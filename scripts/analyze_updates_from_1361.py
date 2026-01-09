"""
Update 1361'den İtibaren Her Update İçin Detaylı Analiz

Bu script:
1. Her update için success oranını hesaplar
2. Her update için başarılı inişlerin başlangıç irtifası ortalamasını hesaplar
3. Sonuçları CSV ve konsola yazdırır
"""

import pandas as pd
import numpy as np
import os
import sys

# Windows encoding fix
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Dosya yolları
if os.path.basename(os.getcwd()) == "scripts":
    BASE_DIR = ".."
else:
    BASE_DIR = "."

MODELS_DIR = os.path.join(BASE_DIR, "models")
DETAILED_LOG_FILE = os.path.join(MODELS_DIR, "detailed_log.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "analyses")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_and_fix_csv(file_path):
    """
    CSV'yi yükle ve sütun kaymasını düzelt
    Header: Episode,Update,Return,Reason,StartAlt,StartDist,Difficulty (7 sütun)
    Gerçek veri: Episode,Update,Return,Reason,StartAlt,StartDist,FinalDist,FinalVel (8 sütun)
    
    NOT: train_main.py'de header 7 sütun ama data 8 sütun yazıyor!
    Gerçek format (satır 200): episode,up,ep_return,reason,start_alt,start_dist,final_dist,final_vel
    """
    print(f"📂 Log dosyası yükleniyor: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ HATA: {file_path} bulunamadı!")
        return None
    
    # CSV'yi 8 sütun olarak oku (header 7 sütun olduğu için hata verir, skip edeceğiz)
    try:
        # Önce header'ı skip edip 8 sütun olarak oku
        df = pd.read_csv(file_path, skiprows=1, header=None, 
                        names=['Episode', 'Update', 'Return', 'Reason', 'StartAlt', 'StartDist', 'FinalDist', 'FinalVel'])
        print(f"   [OK] CSV 8 sütun olarak okundu (header skip edildi)")
    except Exception as e:
        print(f"   [WARN] İlk okuma denemesi başarısız: {e}")
        # Alternatif: error_bad_lines=False ile oku
        try:
            df = pd.read_csv(file_path, on_bad_lines='skip', 
                            names=['Episode', 'Update', 'Return', 'Reason', 'StartAlt', 'StartDist', 'FinalDist', 'FinalVel'])
            print(f"   [OK] CSV error handling ile okundu")
        except Exception as e2:
            print(f"   [ERROR] CSV okunamadı: {e2}")
            return None
    
    # Sütun tiplerini düzelt
    # Update: integer olmalı (0-10000)
    # Return: float
    # Reason: string
    # StartAlt, StartDist, FinalDist, FinalVel: float
    
    # Update sütununu kontrol et ve düzelt
    if 'Update' in df.columns:
        # Update sütunu mantıklı değerler içeriyor mu?
        update_series = pd.to_numeric(df['Update'], errors='coerce')
        
        # Eğer Update sütunu mantıksızsa (çok negatif veya çok büyük), Return ile değiştir
        if (update_series < 0).any() or (update_series > 10000).any() or update_series.isna().all():
            print(f"   [WARN] Update sütunu sorunlu, Return sütunu kontrol ediliyor...")
            # Return sütununu kontrol et
            if 'Return' in df.columns:
                return_as_update = pd.to_numeric(df['Return'], errors='coerce')
                if (return_as_update >= 0).all() and (return_as_update <= 10000).all() and not return_as_update.isna().all():
                    print(f"   [FIX] Update ve Return sütunları yer değiştirmiş, düzeltiliyor...")
                    # Geçici olarak değiştir
                    temp = df['Update'].copy()
                    df['Update'] = df['Return'].copy()
                    df['Return'] = temp
                    print(f"   [OK] Sütunlar düzeltildi")
        
        # Update'i integer'a çevir
        df['Update'] = pd.to_numeric(df['Update'], errors='coerce').astype('Int64')
    
    # Reason sütununu string'e çevir
    if 'Reason' in df.columns:
        df['Reason'] = df['Reason'].astype(str)
    
    # Sayısal sütunları düzelt
    numeric_cols = ['Return', 'StartAlt', 'StartDist', 'FinalDist', 'FinalVel']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    print(f"✓ {len(df)} episode yüklendi")
    if 'Update' in df.columns:
        valid_updates = df['Update'].dropna()
        if len(valid_updates) > 0:
            update_min = int(valid_updates.min())
            update_max = int(valid_updates.max())
            print(f"✓ Update aralığı: {update_min} - {update_max}")
            
            # Update 1361 ve sonrası var mı kontrol et
            updates_1361_plus = valid_updates[valid_updates >= 1361]
            if len(updates_1361_plus) > 0:
                unique_count = len(updates_1361_plus.unique())
                print(f"✓ Update 1361 ve sonrası: {unique_count} unique update bulundu (aralık: {int(updates_1361_plus.min())} - {int(updates_1361_plus.max())})")
            else:
                print(f"⚠ Update 1361 ve sonrası bulunamadı! (Max update: {update_max})")
        else:
            print(f"⚠ Update sütununda geçerli değer bulunamadı!")
    
    return df


def analyze_updates(df, start_update=1361):
    """
    Belirtilen update'den itibaren her update için analiz yap
    """
    print(f"\n🔍 Update {start_update}'den itibaren analiz yapılıyor...")
    
    # Update 1361 ve sonrasını filtrele
    df_filtered = df[df['Update'] >= start_update].copy()
    
    if len(df_filtered) == 0:
        print(f"❌ Update {start_update} ve sonrası için veri bulunamadı!")
        return None
    
    print(f"✓ {len(df_filtered)} episode analiz edilecek")
    print(f"✓ Update aralığı: {df_filtered['Update'].min()} - {df_filtered['Update'].max()}")
    
    # Her update için grupla
    results = []
    updates = sorted(df_filtered['Update'].unique())
    
    for update in updates:
        update_data = df_filtered[df_filtered['Update'] == update]
        
        # Success sayısı ve oranı
        success_count = (update_data['Reason'] == 'Success').sum()
        total_count = len(update_data)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0.0
        
        # Başarılı inişlerin başlangıç irtifası ortalaması
        success_data = update_data[update_data['Reason'] == 'Success']
        if len(success_data) > 0:
            avg_start_alt = success_data['StartAlt'].mean()
            std_start_alt = success_data['StartAlt'].std()
            min_start_alt = success_data['StartAlt'].min()
            max_start_alt = success_data['StartAlt'].max()
        else:
            avg_start_alt = np.nan
            std_start_alt = np.nan
            min_start_alt = np.nan
            max_start_alt = np.nan
        
        # Tüm episode'ların başlangıç irtifası (karşılaştırma için)
        avg_all_start_alt = update_data['StartAlt'].mean()
        
        results.append({
            'Update': update,
            'TotalEpisodes': total_count,
            'SuccessCount': success_count,
            'SuccessRate': success_rate,
            'AvgStartAlt_Success': avg_start_alt,
            'StdStartAlt_Success': std_start_alt,
            'MinStartAlt_Success': min_start_alt,
            'MaxStartAlt_Success': max_start_alt,
            'AvgStartAlt_All': avg_all_start_alt,
        })
    
    results_df = pd.DataFrame(results)
    return results_df


def print_results(results_df):
    """
    Sonuçları konsola yazdır
    """
    print("\n" + "="*100)
    print(f"{'Update':<8} {'Total':<8} {'Success':<10} {'Success%':<12} {'AvgAlt(Succ)':<15} {'StdAlt(Succ)':<15} {'AvgAlt(All)':<15}")
    print("="*100)
    
    for _, row in results_df.iterrows():
        update = int(row['Update'])
        total = int(row['TotalEpisodes'])
        success = int(row['SuccessCount'])
        rate = row['SuccessRate']
        
        if pd.isna(row['AvgStartAlt_Success']):
            avg_alt_succ = "N/A"
            std_alt_succ = "N/A"
        else:
            avg_alt_succ = f"{row['AvgStartAlt_Success']:.2f}m"
            std_alt_succ = f"{row['StdStartAlt_Success']:.2f}m"
        
        avg_alt_all = f"{row['AvgStartAlt_All']:.2f}m"
        
        print(f"{update:<8} {total:<8} {success:<10} {rate:>10.2f}%  {avg_alt_succ:<15} {std_alt_succ:<15} {avg_alt_all:<15}")
    
    print("="*100)
    
    # Özet istatistikler
    print(f"\n📊 ÖZET İSTATİSTİKLER:")
    print(f"   Toplam Update Sayısı: {len(results_df)}")
    print(f"   Ortalama Success Oranı: {results_df['SuccessRate'].mean():.2f}%")
    print(f"   Maksimum Success Oranı: {results_df['SuccessRate'].max():.2f}% (Update {int(results_df.loc[results_df['SuccessRate'].idxmax(), 'Update'])})")
    print(f"   Minimum Success Oranı: {results_df['SuccessRate'].min():.2f}% (Update {int(results_df.loc[results_df['SuccessRate'].idxmin(), 'Update'])})")
    
    # Başarılı inişler için
    success_alt_data = results_df['AvgStartAlt_Success'].dropna()
    if len(success_alt_data) > 0:
        print(f"\n   Başarılı İnişler için Başlangıç İrtifası:")
        print(f"      Ortalama: {success_alt_data.mean():.2f}m")
        print(f"      Std: {success_alt_data.std():.2f}m")
        print(f"      Min: {success_alt_data.min():.2f}m (Update {int(results_df.loc[results_df['AvgStartAlt_Success'].idxmin(), 'Update'])})")
        print(f"      Max: {success_alt_data.max():.2f}m (Update {int(results_df.loc[results_df['AvgStartAlt_Success'].idxmax(), 'Update'])})")


def save_results(results_df, output_dir):
    """
    Sonuçları CSV'ye kaydet
    """
    output_file = os.path.join(output_dir, f"update_analysis_from_1361.csv")
    results_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"\n✓ Sonuçlar kaydedildi: {output_file}")
    return output_file


if __name__ == "__main__":
    print("🚀 Update Analizi Başlatılıyor...\n")
    
    # Veriyi yükle
    df = load_and_fix_csv(DETAILED_LOG_FILE)
    
    if df is None:
        print("❌ Veri yüklenemedi, çıkılıyor.")
        sys.exit(1)
    
    # Analiz yap
    results_df = analyze_updates(df, start_update=1361)
    
    if results_df is None:
        print("❌ Analiz yapılamadı, çıkılıyor.")
        sys.exit(1)
    
    # Sonuçları yazdır
    print_results(results_df)
    
    # CSV'ye kaydet
    save_results(results_df, OUTPUT_DIR)
    
    print("\n✅ Analiz tamamlandı!")
