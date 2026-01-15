"""
Detailed Log CSV Akıllı Segmentasyon Analizi
- Sütun kaymalarını düzeltir
- Training session'larını tespit eder (büyük episode/update reset'leri)
- Geçerli segmentleri belirler
- Özet rapor oluşturur
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path
from collections import Counter

# Windows encoding sorunu için
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Dosya yolları
if os.path.basename(os.getcwd()) == "scripts":
    BASE_DIR = ".."
elif os.path.basename(os.getcwd()) == "analyses":
    BASE_DIR = ".."
else:
    BASE_DIR = "."

MODELS_DIR = os.path.join(BASE_DIR, "models")
ANALYSES_DIR = os.path.join(BASE_DIR, "analyses")
DETAILED_LOG_FILE = os.path.join(MODELS_DIR, "detailed_log.csv")
OUTPUT_DIR = os.path.join(ANALYSES_DIR, "detailed_log_analysis")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_csv_with_fix(file_path):
    """CSV'yi yükle ve sütun kaymasını düzelt"""
    print(f"CSV yükleniyor: {file_path}")
    
    # Önce ilk birkaç satırı oku
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [f.readline().strip() for _ in range(10)]
    
    header = lines[0]
    print(f"Header: {header}")
    print(f"Header sütun sayısı: {len(header.split(','))}")
    
    # İlk veri satırlarını kontrol et
    data_lines = lines[1:6]
    for i, line in enumerate(data_lines):
        cols = line.split(',')
        print(f"Satır {i+2} sütun sayısı: {len(cols)} - Örnek: {line[:80]}")
    
    # CSV'yi yükle (header'ı skip et, manuel oluştur)
    # Önce tüm satırları oku
    all_lines = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            all_lines.append(line.strip())
    
    header_line = all_lines[0]
    data_lines = all_lines[1:]
    
    # En yaygın sütun sayısını bul
    col_counts = Counter([len(line.split(',')) for line in data_lines if line.strip()])
    most_common_cols = col_counts.most_common(1)[0][0]
    print(f"\nEn yaygın sütun sayısı: {most_common_cols}")
    print(f"Sütun sayısı dağılımı: {dict(col_counts.most_common(5))}")
    
    # Verileri parse et
    parsed_data = []
    for line in data_lines:
        if not line.strip():
            continue
        cols = line.split(',')
        if len(cols) == most_common_cols:
            parsed_data.append(cols)
        elif len(cols) > most_common_cols:
            # Fazla sütun varsa, son birkaçını birleştir (virgül içeren string'ler için)
            if len(cols) == most_common_cols + 1:
                # Son iki sütunu birleştir (Reason sütunu virgül içerebilir)
                cols = cols[:most_common_cols-1] + [','.join(cols[most_common_cols-1:])]
                parsed_data.append(cols)
        else:
            # Eksik sütun varsa skip et
            continue
    
    # DataFrame oluştur
    # Format: Episode,Update,Return,Reason,StartAlt,StartDist,final_dist,final_vel
    if most_common_cols == 8:
        column_names = ['Episode', 'Update', 'Return', 'Reason', 'StartAlt', 'StartDist', 'final_dist', 'final_vel']
    elif most_common_cols == 7:
        column_names = ['Episode', 'Update', 'Return', 'Reason', 'StartAlt', 'StartDist', 'Difficulty']
    else:
        # En yaygın format'a göre tahmin et
        column_names = [f'Col{i+1}' for i in range(most_common_cols)]
    
    df = pd.DataFrame(parsed_data, columns=column_names)
    
    # Veri tiplerini düzelt
    df['Episode'] = pd.to_numeric(df['Episode'], errors='coerce')
    df['Update'] = pd.to_numeric(df['Update'], errors='coerce')
    df['Return'] = pd.to_numeric(df['Return'], errors='coerce')
    df['Reason'] = df['Reason'].astype(str).str.strip()
    df['StartAlt'] = pd.to_numeric(df['StartAlt'], errors='coerce')
    df['StartDist'] = pd.to_numeric(df['StartDist'], errors='coerce')
    
    print(f"\n✓ CSV yüklendi: {len(df)} satır")
    print(f"Sütunlar: {list(df.columns)}")
    print(f"\nİlk 5 kayıt:")
    print(df.head().to_string())
    
    return df

def find_training_sessions(df, episode_col='Episode', update_col='Update'):
    """Her Episode 1 başlangıcını yeni training session olarak kabul et"""
    print(f"\n{'='*80}")
    print("TRAINING SESSION TESPİTİ (Episode 1 = Yeni Session)")
    print(f"{'='*80}")
    
    episodes = df[episode_col].values
    updates = df[update_col].values
    
    # Episode 1'den başlayan her kayıt → yeni training session
    sessions = []
    
    print(f"\nEpisode 1 başlangıçlarını tespit ediliyor...")
    print(f"İlk 20 episode: {episodes[:20].tolist()}")
    
    # İlk satır her zaman bir session başlangıcı
    session_starts = [0]
    
    # Episode 1'leri bul (önceki episode 1'den farklıysa veya ilk satırsa)
    for i in range(1, len(df)):
        ep_prev = episodes[i-1]
        ep_curr = episodes[i]
        
        # Skip NaN değerler
        if pd.isna(ep_prev) or pd.isna(ep_curr):
            continue
        
        # Episode 1'e dönüş varsa ve önceki episode 1'den büyükse → yeni session
        if ep_curr == 1 and ep_prev > 1:
            session_starts.append(i)
    
    print(f"\n{len(session_starts)} training session başlangıcı bulundu")
    print(f"İlk 10 session başlangıç satırları: {session_starts[:10]}")
    
    # Her session'ı oluştur
    for idx, start_idx in enumerate(session_starts):
        # Session bitişi: bir sonraki session başlangıcı veya dosya sonu
        end_idx = session_starts[idx + 1] - 1 if idx + 1 < len(session_starts) else len(df) - 1
        
        session = {
            'start_idx': start_idx,
            'end_idx': end_idx,
            'start_episode': int(episodes[start_idx]),
            'end_episode': int(episodes[end_idx]),
            'start_update': int(updates[start_idx]) if not pd.isna(updates[start_idx]) else 0,
            'end_update': int(updates[end_idx]) if not pd.isna(updates[end_idx]) else 0,
            'length': end_idx - start_idx + 1,
            'reason': f"Episode 1 başlangıcı" if idx == 0 else f"Episode {int(episodes[start_idx-1])} → 1"
        }
        sessions.append(session)
    
    print(f"\nToplam {len(sessions)} training session bulundu:\n")
    print(f"{'#':<4} {'Satır':<15} {'Episode':<20} {'Update':<20} {'Kayıt':<10} {'MaxEp':<8} {'Sebep'}")
    print("-" * 110)
    
    for idx, sess in enumerate(sessions, 1):
        ep_range = f"{int(sess['start_episode'])}-{int(sess['end_episode'])}"
        up_range = f"{int(sess['start_update'])}-{int(sess['end_update'])}"
        row_range = f"{sess['start_idx']}-{sess['end_idx']}"
        max_ep = int(sess['end_episode'])
        print(f"{idx:<4} {row_range:<15} {ep_range:<20} {up_range:<20} {sess['length']:<10} {max_ep:<8} {sess.get('reason', 'Normal')}")
    
    return sessions

def analyze_session_quality(df, sessions):
    """Her session'ın kalitesini analiz et"""
    print(f"\n{'='*80}")
    print("SESSION KALİTE ANALİZİ")
    print(f"{'='*80}\n")
    
    session_stats = []
    
    for idx, sess in enumerate(sessions, 1):
        seg_df = df.iloc[sess['start_idx']:sess['end_idx']+1]
        
        total_eps = len(seg_df)
        success_count = (seg_df['Reason'].str.strip() == 'Success').sum()
        success_rate = (success_count / total_eps * 100) if total_eps > 0 else 0
        
        unique_episodes = seg_df['Episode'].nunique()
        avg_return = seg_df['Return'].mean()
        
        session_stats.append({
            'session': idx,
            'total_episodes': total_eps,
            'unique_episodes': unique_episodes,
            'success_count': success_count,
            'success_rate': success_rate,
            'avg_return': avg_return,
            'start_ep': int(sess['start_episode']),
            'end_ep': int(sess['end_episode']),
            'start_up': int(sess['start_update']),
            'end_up': int(sess['end_update']),
        })
    
    print(f"{'#':<4} {'Toplam':<8} {'Unique':<8} {'Success':<10} {'Success%':<10} {'AvgReturn':<12} {'Episode Range':<20}")
    print("-" * 90)
    
    for stat in session_stats:
        ep_range = f"{stat['start_ep']}-{stat['end_ep']}"
        print(f"{stat['session']:<4} {stat['total_episodes']:<8} {stat['unique_episodes']:<8} "
              f"{stat['success_count']:<10} {stat['success_rate']:<8.1f}% {stat['avg_return']:<12.1f} {ep_range:<20}")
    
    return session_stats

def save_session_files(df, sessions, output_dir):
    """Session'ları ayrı dosyalara kaydet"""
    print(f"\n{'='*80}")
    print("SESSION DOSYALARI OLUŞTURULUYOR")
    print(f"{'='*80}\n")
    
    for idx, sess in enumerate(sessions, 1):
        seg_df = df.iloc[sess['start_idx']:sess['end_idx']+1].copy()
        
        filename = f"session_{idx:02d}_ep{int(sess['start_episode'])}-{int(sess['end_episode'])}_up{int(sess['start_update'])}-{int(sess['end_update'])}.csv"
        filepath = os.path.join(output_dir, filename)
        
        seg_df.to_csv(filepath, index=False, encoding='utf-8')
        print(f"✓ Session {idx}: {len(seg_df)} kayıt -> {filename}")
    
    print(f"\n✓ Tüm session'lar kaydedildi: {output_dir}")

def main():
    print("="*80)
    print("DETAILED LOG CSV AKILLI SEGMENTASYON ANALİZİ")
    print("="*80)
    print()
    
    # CSV yükle
    df = load_csv_with_fix(DETAILED_LOG_FILE)
    
    if df is None or len(df) == 0:
        print("❌ CSV yüklenemedi, analiz durduruluyor.")
        return
    
    # Training session'ları bul
    sessions = find_training_sessions(df)
    
    # Session kalitesini analiz et
    session_stats = analyze_session_quality(df, sessions)
    
    # Session dosyalarını kaydet
    save_session_files(df, sessions, OUTPUT_DIR)
    
    # Özet rapor
    report_lines = []
    report_lines.append("="*80)
    report_lines.append("DETAILED LOG CSV SEGMENTASYON RAPORU")
    report_lines.append("="*80)
    report_lines.append("")
    report_lines.append(f"Toplam kayıt: {len(df):,}")
    report_lines.append(f"Unique Episode: {df['Episode'].nunique():,}")
    report_lines.append(f"Unique Update: {df['Update'].nunique():,}")
    report_lines.append(f"Episode aralığı: {df['Episode'].min():.0f} - {df['Episode'].max():.0f}")
    report_lines.append(f"Update aralığı: {df['Update'].min():.0f} - {df['Update'].max():.0f}")
    report_lines.append(f"")
    report_lines.append(f"Training Session sayısı: {len(sessions)}")
    report_lines.append("")
    report_lines.append("SESSION DETAYLARI:")
    for stat in session_stats:
        report_lines.append(f"  Session {stat['session']}: "
                          f"Satır {sessions[stat['session']-1]['start_idx']}-{sessions[stat['session']-1]['end_idx']} | "
                          f"Ep {stat['start_ep']}-{stat['end_ep']} | "
                          f"Up {stat['start_up']}-{stat['end_up']} | "
                          f"{stat['total_episodes']} kayıt | "
                          f"Success: {stat['success_rate']:.1f}% | "
                          f"Avg Return: {stat['avg_return']:.1f}")
    
    report_path = os.path.join(OUTPUT_DIR, "segmentation_report.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f"\n{'='*80}")
    print("ANALİZ TAMAMLANDI!")
    print(f"{'='*80}")
    print(f"\n📄 Rapor kaydedildi: {report_path}")
    print(f"📁 Session dosyaları: {OUTPUT_DIR}")
    print(f"\n💡 ÖNERİLER:")
    print(f"   1. Session dosyalarını inceleyin")
    print(f"   2. Hangileri geçerli eğitim süreçleri belirleyin")
    print(f"   3. Geçerli session'ları birleştirip temiz bir log oluşturun")

if __name__ == "__main__":
    main()
