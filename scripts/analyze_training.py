"""
Training Log Analizi ve Görselleştirme Scripti
Matplotlib ve Seaborn kullanarak detaylı eğitim loglarından grafikler oluşturur
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import sys

# Görsel ayarlar
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'
plt.rcParams['font.size'] = 11

# Dosya yolları (scripts klasöründen çalıştırıldığında üst dizine git)
if os.path.basename(os.getcwd()) == "scripts":
    BASE_DIR = ".."
else:
    BASE_DIR = "."

MODELS_DIR = os.path.join(BASE_DIR, "models")
DETAILED_LOG_FILE = os.path.join(MODELS_DIR, "detailed_log.csv")
UPDATE_LOG_FILE = os.path.join(MODELS_DIR, "update_logs.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "images")

# Çıktı klasörü oluştur
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_data():
    """Log dosyalarını yükle"""
    print("Log dosyaları yükleniyor...")
    
    if not os.path.exists(DETAILED_LOG_FILE):
        print(f"HATA: {DETAILED_LOG_FILE} bulunamadı!")
        return None, None
    
    # Detaylı log
    df_detailed = pd.read_csv(DETAILED_LOG_FILE)
    
    # Update log (varsa)
    df_updates = None
    if os.path.exists(UPDATE_LOG_FILE):
        df_updates = pd.read_csv(UPDATE_LOG_FILE)
    
    print(f"✓ {len(df_detailed)} episode yüklendi")
    if df_updates is not None:
        print(f"✓ {len(df_updates)} update yüklendi")
    
    return df_detailed, df_updates

def plot_success_rate_trend(df):
    """Success rate trendini göster (Update'e göre)"""
    print("1. Success rate trendi oluşturuluyor...")
    
    # Update başına success oranı
    success_by_update = df.groupby('Update').agg({
        'Reason': lambda x: (x == 'Success').sum() / len(x) * 100,
        'Episode': 'count'
    }).reset_index()
    success_by_update.columns = ['Update', 'SuccessRate', 'EpisodeCount']
    success_by_update = success_by_update.sort_values('Update')
    
    # 10-update moving average
    window_size = 10
    if len(success_by_update) >= window_size:
        success_by_update['SuccessRateMA'] = success_by_update['SuccessRate'].rolling(
            window=window_size, min_periods=1).mean()
    else:
        success_by_update['SuccessRateMA'] = success_by_update['SuccessRate']
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Scatter points
    ax.scatter(success_by_update['Update'], success_by_update['SuccessRate'], 
               alpha=0.6, s=30, color='steelblue', label='Success Rate (%)', zorder=2)
    
    # Moving average line
    ax.plot(success_by_update['Update'], success_by_update['SuccessRateMA'], 
            linewidth=2.5, color='crimson', label='10-Update Moving Average', zorder=3)
    
    ax.set_xlabel('Update', fontsize=12, fontweight='bold')
    ax.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('Başarı Oranı Trendi (Update\'e Göre)', fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, max(success_by_update['SuccessRate']) * 1.1])
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "success_rate_trend.png"))
    print(f"   ✓ Kaydedildi: success_rate_trend.png")
    plt.close()

def plot_start_altitude_vs_success(df):
    """Başlangıç irtifası vs Success analizi"""
    print("2. Başlangıç irtifası vs Success analizi oluşturuluyor...")
    
    # Success durumu
    df['IsSuccess'] = df['Reason'] == 'Success'
    
    # İrtifa aralıklarına böl
    bins = [0, 3, 6, 10, 15, 20, np.inf]
    labels = ['0-3m', '3-6m', '6-10m', '10-15m', '15-20m', '20m+']
    df['AltRange'] = pd.cut(df['StartAlt'], bins=bins, labels=labels, include_lowest=True)
    
    # Her irtifa aralığı için success oranı
    alt_success = df.groupby('AltRange').agg({
        'IsSuccess': ['sum', 'count']
    }).reset_index()
    alt_success.columns = ['AltRange', 'SuccessCount', 'TotalCount']
    alt_success['SuccessRate'] = alt_success['SuccessCount'] / alt_success['TotalCount'] * 100
    
    # Sadece veri olan aralıkları al
    alt_success = alt_success[alt_success['TotalCount'] > 0]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Renk gradient (kırmızıdan yeşile)
    colors = plt.cm.RdYlGn(np.linspace(0.3, 0.9, len(alt_success)))
    
    bars = ax.bar(alt_success['AltRange'], alt_success['SuccessRate'], 
                   color=colors, edgecolor='black', linewidth=1.5, alpha=0.8)
    
    # Değerleri üzerine yaz
    for i, (rate, count, total) in enumerate(zip(alt_success['SuccessRate'], 
                                                   alt_success['SuccessCount'], 
                                                   alt_success['TotalCount'])):
        ax.text(i, rate + max(alt_success['SuccessRate']) * 0.03, 
                f'{rate:.1f}%\n({int(count)}/{int(total)})',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_xlabel('Başlangıç İrtifa Aralığı', fontsize=12, fontweight='bold')
    ax.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('Başlangıç İrtifasına Göre Başarı Oranı', fontsize=14, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim([0, max(alt_success['SuccessRate']) * 1.2])
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "start_altitude_vs_success.png"))
    print(f"   ✓ Kaydedildi: start_altitude_vs_success.png")
    plt.close()

def plot_scatter_start_altitude_success(df):
    """Başlangıç irtifası vs Success scatter plot (zaman serisi)"""
    print("3. Başlangıç irtifası scatter plot oluşturuluyor...")
    
    # Success ve Failure'ları ayır
    df_success = df[df['Reason'] == 'Success'].copy()
    df_failure = df[df['Reason'] != 'Success'].copy()
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Failure points (şeffaf, küçük)
    ax.scatter(df_failure['Episode'], df_failure['StartAlt'], 
               s=15, alpha=0.3, color='crimson', label='Failure', zorder=1)
    
    # Success points (belirgin)
    ax.scatter(df_success['Episode'], df_success['StartAlt'], 
               s=25, alpha=0.7, color='forestgreen', label='Success', zorder=2, edgecolors='darkgreen')
    
    ax.set_xlabel('Episode', fontsize=12, fontweight='bold')
    ax.set_ylabel('Başlangıç İrtifası (m)', fontsize=12, fontweight='bold')
    ax.set_title('Başlangıç İrtifası vs Başarı (Zaman Serisi)', fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "start_altitude_scatter.png"))
    print(f"   ✓ Kaydedildi: start_altitude_scatter.png")
    plt.close()

def plot_termination_reasons(df):
    """Termination reason dağılımı"""
    print("4. Termination reason dağılımı oluşturuluyor...")
    
    reason_counts = df['Reason'].value_counts()
    
    # En çok görülen 8 sebep
    top_n = min(8, len(reason_counts))
    reason_counts = reason_counts.head(top_n)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Pasta grafiği
    colors = sns.color_palette("Set2", len(reason_counts))
    wedges, texts, autotexts = ax.pie(reason_counts.values, labels=reason_counts.index, 
                                       autopct='%1.1f%%', startangle=90,
                                       colors=colors, textprops={'fontsize': 11})
    
    # Yüzde değerlerini kalın yap
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)
    
    ax.set_title('Episode Sonlanma Sebepleri Dağılımı', fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "termination_reasons.png"))
    print(f"   ✓ Kaydedildi: termination_reasons.png")
    plt.close()

def plot_loss_trend(df_updates):
    """Loss trendi (Update'e göre)"""
    if df_updates is None:
        print("   ⚠ Update log dosyası bulunamadı, atlanıyor...")
        return
    
    print("5. Loss trendi oluşturuluyor...")
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    
    # Total Loss
    axes[0].plot(df_updates['Update'], df_updates['Loss'], 
                 linewidth=2, color='steelblue')
    axes[0].set_xlabel('Update', fontsize=11, fontweight='bold')
    axes[0].set_ylabel('Total Loss', fontsize=11, fontweight='bold')
    axes[0].set_title('Total Loss Trendi', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    
    # Policy Loss & Value Loss
    axes[1].plot(df_updates['Update'], df_updates['PolicyLoss'], 
                 linewidth=2, color='forestgreen', label='Policy Loss')
    axes[1].plot(df_updates['Update'], df_updates['ValueLoss'], 
                 linewidth=2, color='coral', label='Value Loss')
    axes[1].set_xlabel('Update', fontsize=11, fontweight='bold')
    axes[1].set_ylabel('Loss', fontsize=11, fontweight='bold')
    axes[1].set_title('Policy Loss ve Value Loss Trendi', fontsize=12, fontweight='bold')
    axes[1].legend(loc='best', framealpha=0.9)
    axes[1].grid(True, alpha=0.3)
    
    fig.suptitle('Loss Trendi (Update\'e Göre)', fontsize=14, fontweight='bold', y=0.995)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "loss_trend.png"))
    print(f"   ✓ Kaydedildi: loss_trend.png")
    plt.close()

def plot_return_distribution(df):
    """Return dağılımı (Success vs Failure)"""
    print("6. Return dağılımı oluşturuluyor...")
    
    df['IsSuccess'] = df['Reason'] == 'Success'
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Histogram edges
    return_min = df['Return'].min()
    return_max = df['Return'].max()
    bins = np.linspace(return_min, return_max, 50)
    
    # Success returns
    ax.hist(df[df['IsSuccess']]['Return'], bins=bins, alpha=0.7, 
            color='forestgreen', label='Success', edgecolor='black', linewidth=0.5)
    
    # Failure returns
    ax.hist(df[~df['IsSuccess']]['Return'], bins=bins, alpha=0.7, 
            color='crimson', label='Failure', edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('Return', fontsize=12, fontweight='bold')
    ax.set_ylabel('Frekans', fontsize=12, fontweight='bold')
    ax.set_title('Return Dağılımı (Success vs Failure)', fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "return_distribution.png"))
    print(f"   ✓ Kaydedildi: return_distribution.png")
    plt.close()

def print_summary_statistics(df):
    """Özet istatistikleri yazdır"""
    print("\n" + "=" * 60)
    print("ÖZET İSTATİSTİKLER")
    print("=" * 60)
    
    is_success = df['Reason'] == 'Success'
    
    print(f"Toplam Episode: {len(df)}")
    print(f"Success Oranı: {sum(is_success) / len(df) * 100:.2f}%")
    print(f"Ortalama Başlangıç İrtifası: {df['StartAlt'].mean():.2f} m")
    print(f"Success olanların ort. başlangıç irtifası: {df[is_success]['StartAlt'].mean():.2f} m")
    print(f"Failure olanların ort. başlangıç irtifası: {df[~is_success]['StartAlt'].mean():.2f} m")
    
    print("\nTermination Reason Dağılımı:")
    reason_counts = df['Reason'].value_counts()
    for reason, count in reason_counts.items():
        print(f"  {reason:15s}: {count:5d} ({count/len(df)*100:5.1f}%)")

def main():
    print("=" * 60)
    print("TRAINING LOG ANALİZİ VE GÖRSELLEŞTİRME")
    print("=" * 60)
    print()
    
    # Veri yükle
    df_detailed, df_updates = load_data()
    
    if df_detailed is None:
        print("\nHATA: Veri yüklenemedi!")
        return
    
    print(f"\nGrafikler oluşturuluyor...")
    print("-" * 60)
    
    # Grafikleri oluştur
    plot_success_rate_trend(df_detailed)
    plot_start_altitude_vs_success(df_detailed)
    plot_scatter_start_altitude_success(df_detailed)
    plot_termination_reasons(df_detailed)
    plot_loss_trend(df_updates)
    plot_return_distribution(df_detailed)
    print_summary_statistics(df_detailed)
    
    print("-" * 60)
    print(f"\n✓ Tüm grafikler oluşturuldu!")
    print(f"📊 Görseller '{OUTPUT_DIR}' klasöründe PNG formatında kaydedildi.")
    print("   Bu görseller README.md dosyasına eklenebilir.")

if __name__ == "__main__":
    main()
