"""
İtki Analizi: Başarılı İniş Olasılığı ve İtki Aralığı Analizi

Bu script:
1. Farklı başlangıç irtifaları için teorik başarılı iniş analizi yapar
2. Model'in gerçek itki kullanımını analiz eder (state_log.csv)
3. İrtifa-zaman serisi grafikleri çizer
4. Başarılı iniş olasılığını başlangıç irtifasına göre gösterir
5. İtki aralığı kullanım dağılımını gösterir
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys

# Windows encoding fix
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# FİZİK PARAMETRELERİ
MASS = 1000.0  # kg
MAX_THRUST = 15000.0  # N (kullanıcı 15k dedi, Unity'de 20k var ama 15k ile test edelim)
GRAVITY = 9.81  # m/s²
LINEAR_DAMPING = 0.05  # Unity'de ~0.05-0.1 arası

# Landing criteria (env.py'den)
LANDING_HEIGHT = 1.7  # m
MAX_LANDING_VY = 3.5  # m/s (aşağı)
MAX_LANDING_VH = 3.0  # m/s (yatay)
ZONE_RADIUS = 15.0  # m

# Grafik stil
plt.style.use('dark_background')
sns.set_palette("husl")

OUTPUT_DIR = "images"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)


def physics_simulate(initial_altitude, thrust_profile_func, dt=0.02, max_time=60.0):
    """
    Fizik simülasyonu: Belirli bir thrust profili ile iniş simülasyonu
    
    Args:
        initial_altitude: Başlangıç irtifası (m)
        thrust_profile_func: t -> thrust_ratio (0-1) fonksiyonu
        dt: Time step (s)
        max_time: Max simülasyon süresi (s)
    
    Returns:
        success: Başarılı iniş mi? (bool)
        trajectory: [[t, y, vy, thrust], ...] array
        landing_info: {'altitude': float, 'vy': float, 'vh': float, 'dist': float}
    """
    # Initial conditions
    y = initial_altitude  # m
    vy = 0.0  # m/s (başlangıçta durgun)
    x = 0.0  # m (merkeze başla)
    vx = 0.0  # m/s
    z = 0.0
    vz = 0.0
    
    trajectory = []
    t = 0.0
    
    while t < max_time:
        # Thrust ratio (0-1)
        thrust_ratio = thrust_profile_func(t)
        thrust_force = MAX_THRUST * thrust_ratio  # N
        
        # Net force (yukarı yön pozitif)
        weight = MASS * GRAVITY  # N (aşağı)
        net_force = thrust_force - weight  # N (yukarı)
        net_acceleration = net_force / MASS  # m/s²
        
        # Velocity update (damping ile)
        vy += net_acceleration * dt
        vy *= (1.0 - LINEAR_DAMPING * dt)  # Linear damping
        
        # Position update
        y += vy * dt
        
        # Horizontal (simplified - sadece drift için)
        # Basit sürtünme modeli
        vx *= (1.0 - LINEAR_DAMPING * dt)
        x += vx * dt
        
        trajectory.append([t, y, vy, thrust_ratio, x])
        
        # Landing check
        if y <= LANDING_HEIGHT:
            vh = abs(vx)  # Basitleştirilmiş yatay hız
            dist_h = abs(x)
            
            landing_info = {
                'altitude': y,
                'vy': vy,
                'vh': vh,
                'dist': dist_h,
                'time': t
            }
            
            # Success criteria
            success = (
                y <= LANDING_HEIGHT and
                abs(vy) <= MAX_LANDING_VY and
                vh <= MAX_LANDING_VH and
                dist_h <= ZONE_RADIUS
            )
            
            return success, np.array(trajectory), landing_info
        
        # Out of bounds check
        if y < 0 or abs(x) > 50:
            return False, np.array(trajectory), None
        
        t += dt
    
    # Time limit
    return False, np.array(trajectory), None


def optimal_thrust_profile_bang_bang(initial_altitude, t):
    """
    Basit bang-bang control: Yüksek irtifada max thrust, düşük irtifada azalt
    Optimal değil ama basit referans
    """
    # Simülasyon içinde yüksekliği hesaplayamayız, basit zaman bazlı
    if t < 5.0:  # İlk 5 saniye max thrust
        return 1.0
    elif t < 15.0:  # Sonra orta
        return 0.6
    else:  # Son düşük
        return 0.3


def pid_like_thrust_profile(initial_altitude, t, target_vy=-2.0):
    """
    PID-benzeri kontrol: Hedef dikey hıza göre thrust ayarla
    Basit versiyon
    """
    # Time-based approximation (gerçekte state'e göre olmalı)
    if t < 3.0:
        return 1.0  # Max thrust başlangıçta
    else:
        # Yavaşça azalt
        return max(0.2, 1.0 - (t - 3.0) * 0.05)


def analyze_thrust_range_from_model():
    """
    Model'in gerçek itki kullanımını analiz et (state_log.csv'den)
    """
    state_log_path = os.path.join("models", "state_log.csv")
    
    if not os.path.exists(state_log_path):
        print(f"⚠ state_log.csv bulunamadı: {state_log_path}")
        return None
    
    print("📊 Model verilerini yükleniyor...")
    df = pd.read_csv(state_log_path)
    
    # Thrust değerleri (zaten 0-1 normalize)
    thrusts = df['thrust'].values
    altitudes = df['dy'].values
    velocities = df['vy'].values
    
    # İrtifa bölgelerine göre thrust analizi
    altitude_bins = [0, 5, 10, 15, 20, 30, 50]
    altitude_labels = ['0-5m', '5-10m', '10-15m', '15-20m', '20-30m', '30m+']
    
    results = []
    for i in range(len(altitude_bins) - 1):
        mask = (altitudes >= altitude_bins[i]) & (altitudes < altitude_bins[i+1])
        if np.sum(mask) > 0:
            thrusts_in_bin = thrusts[mask]
            results.append({
                'altitude_range': altitude_labels[i],
                'mean_thrust': np.mean(thrusts_in_bin),
                'median_thrust': np.median(thrusts_in_bin),
                'std_thrust': np.std(thrusts_in_bin),
                'min_thrust': np.min(thrusts_in_bin),
                'max_thrust': np.max(thrusts_in_bin),
                'count': len(thrusts_in_bin)
            })
    
    return pd.DataFrame(results), df


def plot_thrust_analysis(df_model_data=None):
    """
    İtki analizi grafikleri
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('İtki Analizi: Başarılı İniş Olasılığı ve İtki Kullanımı', 
                 fontsize=16, fontweight='bold')
    
    # 1. Teorik Başarılı İniş Olasılığı (Farklı thrust profilleri)
    print("🔬 Teorik simülasyonlar çalıştırılıyor...")
    initial_altitudes = np.arange(5, 26, 1)  # 5-25m
    profiles = [
        ('Max Thrust (1.0)', lambda t: 1.0),
        ('Optimal Bang-Bang', lambda t: optimal_thrust_profile_bang_bang(20, t)),
        ('PID-Like', lambda t: pid_like_thrust_profile(20, t)),
        ('Medium (0.6)', lambda t: 0.6),
        ('Low (0.3)', lambda t: 0.3),
    ]
    
    ax1 = axes[0, 0]
    for profile_name, profile_func in profiles:
        success_rates = []
        for alt in initial_altitudes:
            success, traj, info = physics_simulate(alt, profile_func)
            success_rates.append(1.0 if success else 0.0)
        
        ax1.plot(initial_altitudes, success_rates, marker='o', label=profile_name, linewidth=2)
    
    ax1.set_xlabel('Başlangıç İrtifası (m)', fontsize=11)
    ax1.set_ylabel('Başarılı İniş', fontsize=11)
    ax1.set_title('Teorik Başarılı İniş Olasılığı (Farklı Thrust Profilleri)', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim([-0.1, 1.1])
    
    # 2. İrtifa-Zaman Serisi (Teorik - Başarılı iniş örneği)
    ax2 = axes[0, 1]
    test_altitude = 15.0
    success, traj, info = physics_simulate(test_altitude, 
                                           lambda t: optimal_thrust_profile_bang_bang(test_altitude, t))
    
    if len(traj) > 0:
        ax2.plot(traj[:, 0], traj[:, 1], 'g-', linewidth=2, label='İrtifa')
        ax2.axhline(y=LANDING_HEIGHT, color='r', linestyle='--', linewidth=1, label=f'Landing ({LANDING_HEIGHT}m)')
        ax2.fill_between(traj[:, 0], 0, LANDING_HEIGHT, alpha=0.2, color='red')
        ax2.set_xlabel('Zaman (s)', fontsize=11)
        ax2.set_ylabel('İrtifa (m)', fontsize=11)
        ax2.set_title(f'İrtifa-Zaman Serisi (Başlangıç: {test_altitude}m, Thrust: Optimal)', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Success bilgisi
        if success:
            ax2.text(0.5, 0.95, f'✓ Başarılı\nVy: {info["vy"]:.2f} m/s', 
                    transform=ax2.transAxes, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='green', alpha=0.3))
        else:
            ax2.text(0.5, 0.95, f'✗ Başarısız', 
                    transform=ax2.transAxes, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='red', alpha=0.3))
    
    # 3. Model'in İtki Kullanımı (İrtifa Bölgelerine Göre)
    if df_model_data is not None:
        ax3 = axes[1, 0]
        
        # İrtifa bölgelerine göre thrust dağılımı
        altitude_ranges = ['0-5m', '5-10m', '10-15m', '15-20m', '20-30m', '30m+']
        df_summary, df_full = df_model_data
        
        if df_summary is not None and len(df_summary) > 0:
            x_pos = np.arange(len(df_summary))
            width = 0.6
            
            ax3.bar(x_pos, df_summary['mean_thrust'], width, 
                   yerr=df_summary['std_thrust'], capsize=5,
                   label='Ortalama Thrust', alpha=0.8)
            ax3.axhline(y=1.0, color='r', linestyle='--', linewidth=1, label='Max Thrust (1.0)')
            ax3.axhline(y=0.5, color='orange', linestyle='--', linewidth=1, label='Orta Thrust (0.5)')
            
            ax3.set_xlabel('İrtifa Bölgesi', fontsize=11)
            ax3.set_ylabel('Thrust Ratio (0-1)', fontsize=11)
            ax3.set_title('Model İtki Kullanımı (İrtifa Bölgelerine Göre)', fontsize=12)
            ax3.set_xticks(x_pos)
            ax3.set_xticklabels(df_summary['altitude_range'], rotation=45, ha='right')
            ax3.legend()
            ax3.grid(True, alpha=0.3, axis='y')
            ax3.set_ylim([0, 1.1])
        
        # 4. Thrust Histogram (Tüm veriler)
        ax4 = axes[1, 1]
        if df_full is not None and len(df_full) > 0:
            thrusts = df_full['thrust'].values
            ax4.hist(thrusts, bins=50, alpha=0.7, edgecolor='black', linewidth=0.5)
            ax4.axvline(x=np.mean(thrusts), color='r', linestyle='--', linewidth=2, 
                       label=f'Ortalama: {np.mean(thrusts):.3f}')
            ax4.axvline(x=np.median(thrusts), color='orange', linestyle='--', linewidth=2,
                       label=f'Medyan: {np.median(thrusts):.3f}')
            ax4.set_xlabel('Thrust Ratio (0-1)', fontsize=11)
            ax4.set_ylabel('Frekans', fontsize=11)
            ax4.set_title('Model İtki Kullanım Dağılımı', fontsize=12)
            ax4.legend()
            ax4.grid(True, alpha=0.3, axis='y')
    else:
        ax3.text(0.5, 0.5, 'Model verisi yok\n(state_log.csv bulunamadı)', 
                transform=ax3.transAxes, ha='center', va='center', fontsize=12)
        ax4.text(0.5, 0.5, 'Model verisi yok\n(state_log.csv bulunamadı)', 
                transform=ax4.transAxes, ha='center', va='center', fontsize=12)
    
    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, "thrust_analysis.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Grafik kaydedildi: {output_path}")
    
    return fig


def print_summary(df_model_data=None):
    """
    Özet istatistikler yazdır
    """
    print("\n" + "="*70)
    print("İTKI ANALİZİ ÖZET")
    print("="*70)
    
    print(f"\n📐 Fizik Parametreleri:")
    print(f"   Kütle: {MASS} kg")
    print(f"   Max İtki: {MAX_THRUST} N")
    print(f"   Yerçekimi: {GRAVITY} m/s²")
    print(f"   Net Max İvme (yukarı): {(MAX_THRUST - MASS*GRAVITY)/MASS:.2f} m/s²")
    
    if df_model_data is not None:
        df_summary, df_full = df_model_data
        if df_summary is not None:
            print(f"\n📊 Model İtki Kullanım Özeti:")
            for _, row in df_summary.iterrows():
                print(f"   {row['altitude_range']:10s}: "
                      f"Ort={row['mean_thrust']:.3f}, "
                      f"Med={row['median_thrust']:.3f}, "
                      f"Std={row['std_thrust']:.3f}, "
                      f"N={row['count']}")
        
        if df_full is not None:
            print(f"\n📈 Genel İtki İstatistikleri:")
            print(f"   Ortalama: {df_full['thrust'].mean():.3f}")
            print(f"   Medyan: {df_full['thrust'].median():.3f}")
            print(f"   Std: {df_full['thrust'].std():.3f}")
            print(f"   Min: {df_full['thrust'].min():.3f}")
            print(f"   Max: {df_full['thrust'].max():.3f}")
            print(f"   Toplam adım sayısı: {len(df_full)}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    print("🚀 İtki Analizi Başlatılıyor...\n")
    
    # Model verilerini yükle
    df_model_data = analyze_thrust_range_from_model()
    
    # Grafikleri oluştur
    plot_thrust_analysis(df_model_data)
    
    # Özet yazdır
    print_summary(df_model_data)
    
    print("\n✅ Analiz tamamlandı!")
