"""
Session Bazlı Training Analizi ve Görselleştirme
Training session'larını analiz eder ve curriculum learning progress'i gösterir
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import sys
import glob

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Görsel ayarlar
try:
    plt.style.use('seaborn-v0_8-darkgrid')
except:
    try:
        plt.style.use('seaborn-darkgrid')
    except:
        plt.style.use('dark_background')
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3

sns.set_palette("husl")
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'
plt.rcParams['font.size'] = 11

# Dosya yolları
if os.path.basename(os.getcwd()) == "scripts":
    BASE_DIR = ".."
elif os.path.basename(os.getcwd()) == "analyses":
    BASE_DIR = ".."
else:
    BASE_DIR = "."

SESSION_DIR = os.path.join(BASE_DIR, "analyses", "detailed_log_analysis")
OUTPUT_DIR = os.path.join(BASE_DIR, "images")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_all_sessions(session_dir):
    """Tüm session CSV dosyalarını yükle ve analiz et"""
    session_files = sorted(glob.glob(os.path.join(session_dir, "session_*.csv")))
    
    sessions_data = []
    
    for session_file in session_files:
        try:
            df = pd.read_csv(session_file)
            
            # Veri tiplerini düzelt
            df['Episode'] = pd.to_numeric(df['Episode'], errors='coerce')
            df['Update'] = pd.to_numeric(df['Update'], errors='coerce')
            df['Return'] = pd.to_numeric(df['Return'], errors='coerce')
            df['Reason'] = df['Reason'].astype(str).str.strip()
            df['StartAlt'] = pd.to_numeric(df['StartAlt'], errors='coerce')
            df['StartDist'] = pd.to_numeric(df['StartDist'], errors='coerce')
            if 'final_dist' in df.columns:
                df['final_dist'] = pd.to_numeric(df['final_dist'], errors='coerce')
            if 'final_vel' in df.columns:
                df['final_vel'] = pd.to_numeric(df['final_vel'], errors='coerce')
            
            # Session bilgilerini çıkar
            session_name = os.path.basename(session_file)
            session_num = int(session_name.split('_')[1])
            
            total_episodes = len(df)
            success_count = (df['Reason'] == 'Success').sum()
            success_rate = (success_count / total_episodes * 100) if total_episodes > 0 else 0
            avg_return = df['Return'].mean()
            avg_start_alt = df['StartAlt'].mean()
            
            start_update = df['Update'].min()
            end_update = df['Update'].max()
            
            sessions_data.append({
                'session_num': session_num,
                'session_name': session_name,
                'total_episodes': total_episodes,
                'success_count': success_count,
                'success_rate': success_rate,
                'avg_return': avg_return,
                'avg_start_alt': avg_start_alt,
                'start_update': start_update,
                'end_update': end_update,
                'update_range': end_update - start_update,
                'df': df
            })
        except Exception as e:
            print(f"⚠️  Hata ({session_file}): {e}")
            continue
    
    # Session numarasına göre sırala
    sessions_data.sort(key=lambda x: x['session_num'])
    
    return sessions_data

def plot_curriculum_progression(sessions_data):
    """Curriculum Learning Progress: Update bazlı success rate trendi"""
    print("1. Curriculum Learning Progress grafiği oluşturuluyor...")
    
    # Tüm session'ları birleştir, update'e göre sırala
    all_data = []
    for sess in sessions_data:
        df = sess['df']
        for _, row in df.iterrows():
            if pd.notna(row['Update']):
                all_data.append({
                    'Update': row['Update'],
                    'Success': 1 if row['Reason'] == 'Success' else 0,
                    'Return': row['Return'],
                    'StartAlt': row['StartAlt'],
                    'Session': sess['session_num']
                })
    
    if len(all_data) == 0:
        print("   [WARN] Veri bulunamadı!")
        return
    
    df_all = pd.DataFrame(all_data)
    
    # Update'e göre rolling success rate (window=100)
    df_all = df_all.sort_values('Update')
    df_all['RollingSuccessRate'] = df_all['Success'].rolling(window=100, center=True).mean() * 100
    df_all['RollingAvgReturn'] = df_all['Return'].rolling(window=100, center=True).mean()
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # 1. Success Rate Trend
    ax1.plot(df_all['Update'], df_all['RollingSuccessRate'], 
             linewidth=2, color='#2ecc71', label='Success Rate (100-ep rolling avg)')
    ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='50% Threshold')
    ax1.set_xlabel('Update', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Curriculum Learning Progress: Success Rate Over Training', 
                  fontsize=14, fontweight='bold', pad=15)
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim([0, 105])
    
    # 2. Average Return Trend
    ax2.plot(df_all['Update'], df_all['RollingAvgReturn'], 
             linewidth=2, color='#3498db', label='Average Return (100-ep rolling avg)')
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax2.set_xlabel('Update', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Average Return', fontsize=12, fontweight='bold')
    ax2.set_title('Curriculum Learning Progress: Average Return Over Training',
                  fontsize=14, fontweight='bold', pad=15)
    ax2.legend(loc='best')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "curriculum_progression.png"))
    print(f"   [OK] Kaydedildi: curriculum_progression.png")
    plt.close()

def plot_session_performance_timeline(sessions_data):
    """Session Performance Timeline: Her session'ın başarı metriklerini göster"""
    print("2. Session Performance Timeline grafiği oluşturuluyor...")
    
    sessions_df = pd.DataFrame([
        {
            'Session': s['session_num'],
            'SuccessRate': s['success_rate'],
            'AvgReturn': s['avg_return'],
            'AvgStartAlt': s['avg_start_alt'],
            'EpisodeCount': s['total_episodes'],
            'UpdateRange': s['update_range']
        }
        for s in sessions_data
    ])
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # 1. Success Rate by Session
    colors = ['#e74c3c' if x < 30 else '#f39c12' if x < 60 else '#2ecc71' 
              for x in sessions_df['SuccessRate']]
    
    bars1 = ax1.bar(sessions_df['Session'], sessions_df['SuccessRate'], 
                     color=colors, alpha=0.7, edgecolor='black', linewidth=1)
    ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='50% Threshold')
    ax1.set_xlabel('Session Number', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Training Session Performance: Success Rate by Session',
                  fontsize=14, fontweight='bold', pad=15)
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_ylim([0, 105])
    
    # 2. Average Return by Session
    ax2.bar(sessions_df['Session'], sessions_df['AvgReturn'], 
            color='#3498db', alpha=0.7, edgecolor='black', linewidth=1)
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax2.set_xlabel('Session Number', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Average Return', fontsize=12, fontweight='bold')
    ax2.set_title('Training Session Performance: Average Return by Session',
                  fontsize=14, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "session_performance_timeline.png"))
    print(f"   [OK] Kaydedildi: session_performance_timeline.png")
    plt.close()

def plot_landing_quality_analysis(sessions_data):
    """Final Landing Quality: final_dist ve final_vel analizi"""
    print("3. Landing Quality Analysis grafiği oluşturuluyor...")
    
    # Tüm başarılı inişleri topla
    successful_landings = []
    for sess in sessions_data:
        df = sess['df']
        successful = df[df['Reason'] == 'Success'].copy()
        if 'final_dist' in successful.columns and 'final_vel' in successful.columns:
            for _, row in successful.iterrows():
                if pd.notna(row['final_dist']) and pd.notna(row['final_vel']):
                    successful_landings.append({
                        'final_dist': row['final_dist'],
                        'final_vel': row['final_vel'],
                        'StartAlt': row['StartAlt'],
                        'Return': row['Return'],
                        'Update': row['Update']
                    })
    
    if len(successful_landings) == 0:
        print("   [WARN] Başarılı iniş verisi bulunamadı!")
        return
    
    df_landings = pd.DataFrame(successful_landings)
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 12))
    
    # 1. Final Distance Distribution
    ax1.hist(df_landings['final_dist'], bins=50, color='#3498db', alpha=0.7, edgecolor='black')
    ax1.axvline(x=df_landings['final_dist'].median(), color='red', linestyle='--', 
                linewidth=2, label=f'Median: {df_landings["final_dist"].median():.2f}m')
    ax1.set_xlabel('Final Distance from Center (m)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax1.set_title('Landing Accuracy: Final Distance Distribution', fontsize=12, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # 2. Final Velocity Distribution
    ax2.hist(df_landings['final_vel'], bins=50, color='#e74c3c', alpha=0.7, edgecolor='black')
    ax2.axvline(x=df_landings['final_vel'].median(), color='blue', linestyle='--', 
                linewidth=2, label=f'Median: {df_landings["final_vel"].median():.2f} m/s')
    ax2.set_xlabel('Final Vertical Velocity (m/s)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax2.set_title('Landing Quality: Final Vertical Velocity Distribution', 
                  fontsize=12, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    # 3. Distance vs Velocity Scatter
    scatter = ax3.scatter(df_landings['final_dist'], df_landings['final_vel'], 
                          c=df_landings['Return'], cmap='viridis', alpha=0.6, s=20)
    ax3.set_xlabel('Final Distance from Center (m)', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Final Vertical Velocity (m/s)', fontsize=11, fontweight='bold')
    ax3.set_title('Landing Quality: Distance vs Velocity (colored by Return)',
                  fontsize=12, fontweight='bold')
    plt.colorbar(scatter, ax=ax3, label='Return')
    ax3.grid(True, alpha=0.3)
    
    # 4. Landing Quality Over Updates
    df_landings_sorted = df_landings.sort_values('Update')
    window = 100
    df_landings_sorted['RollingAvgDist'] = df_landings_sorted['final_dist'].rolling(window=window).mean()
    df_landings_sorted['RollingAvgVel'] = df_landings_sorted['final_vel'].rolling(window=window).mean()
    
    ax4_twin = ax4.twinx()
    line1 = ax4.plot(df_landings_sorted['Update'], df_landings_sorted['RollingAvgDist'],
                     color='#3498db', linewidth=2, label='Avg Distance')
    line2 = ax4_twin.plot(df_landings_sorted['Update'], df_landings_sorted['RollingAvgVel'],
                          color='#e74c3c', linewidth=2, label='Avg Velocity')
    
    ax4.set_xlabel('Update', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Average Distance (m)', fontsize=11, fontweight='bold', color='#3498db')
    ax4_twin.set_ylabel('Average Velocity (m/s)', fontsize=11, fontweight='bold', color='#e74c3c')
    ax4.set_title('Landing Quality Improvement Over Training',
                  fontsize=12, fontweight='bold')
    ax4.tick_params(axis='y', labelcolor='#3498db')
    ax4_twin.tick_params(axis='y', labelcolor='#e74c3c')
    ax4.grid(True, alpha=0.3)
    
    # Legend
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax4.legend(lines, labels, loc='best')
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "landing_quality_analysis.png"))
    print(f"   [OK] Kaydedildi: landing_quality_analysis.png")
    plt.close()

def plot_start_altitude_progression(sessions_data):
    """Start Altitude Progression: Curriculum learning'de irtifa artışı"""
    print("4. Start Altitude Progression grafiği oluşturuluyor...")
    
    # Her session için ortalama başlangıç irtifası
    sessions_summary = []
    for sess in sessions_data:
        df = sess['df']
        for update in df['Update'].unique():
            if pd.notna(update):
                update_df = df[df['Update'] == update]
                sessions_summary.append({
                    'Update': update,
                    'AvgStartAlt': update_df['StartAlt'].mean(),
                    'SuccessRate': (update_df['Reason'] == 'Success').mean() * 100,
                    'Session': sess['session_num']
                })
    
    if len(sessions_summary) == 0:
        print("   [WARN] Veri bulunamadı!")
        return
    
    df_summary = pd.DataFrame(sessions_summary).sort_values('Update')
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # 1. Average Start Altitude Over Updates
    df_grouped = df_summary.groupby('Update').agg({
        'AvgStartAlt': 'mean',
        'SuccessRate': 'mean'
    }).reset_index()
    
    ax1.plot(df_grouped['Update'], df_grouped['AvgStartAlt'], 
             linewidth=2, color='#9b59b6', marker='o', markersize=3)
    ax1.set_xlabel('Update', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Average Start Altitude (m)', fontsize=12, fontweight='bold')
    ax1.set_title('Curriculum Learning: Start Altitude Progression',
                  fontsize=14, fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(bottom=0)
    
    # 2. Success Rate vs Start Altitude
    scatter = ax2.scatter(df_grouped['AvgStartAlt'], df_grouped['SuccessRate'],
                          c=df_grouped['Update'], cmap='coolwarm', s=50, alpha=0.6)
    ax2.set_xlabel('Average Start Altitude (m)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax2.set_title('Success Rate at Different Start Altitudes',
                  fontsize=14, fontweight='bold', pad=15)
    plt.colorbar(scatter, ax=ax2, label='Update')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 105])
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "start_altitude_progression.png"))
    print(f"   [OK] Kaydedildi: start_altitude_progression.png")
    plt.close()

def plot_session_success_rates(sessions_data):
    """Session bazlı detaylı success oranı analizi"""
    print("5. Session Success Rates grafiği oluşturuluyor...")
    
    sessions_df = pd.DataFrame([
        {
            'Session': s['session_num'],
            'SuccessRate': s['success_rate'],
            'SuccessCount': s['success_count'],
            'TotalEpisodes': s['total_episodes'],
            'AvgReturn': s['avg_return'],
            'StartUpdate': s['start_update'],
            'EndUpdate': s['end_update']
        }
        for s in sessions_data
    ])
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # 1. Success Rate by Session (Bar Chart with episode count annotation)
    colors = ['#e74c3c' if x < 30 else '#f39c12' if x < 60 else '#2ecc71' 
              for x in sessions_df['SuccessRate']]
    
    bars = ax1.bar(sessions_df['Session'], sessions_df['SuccessRate'], 
                   color=colors, alpha=0.7, edgecolor='black', linewidth=1)
    
    # Episode sayılarını üzerine yaz
    for i, (bar, episodes, success_rate) in enumerate(zip(bars, sessions_df['TotalEpisodes'], sessions_df['SuccessRate'])):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{episodes} ep',
                ha='center', va='bottom', fontsize=8, rotation=90)
    
    ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='50% Threshold')
    ax1.set_xlabel('Session Number', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Session Success Rates with Episode Counts',
                  fontsize=14, fontweight='bold', pad=15)
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_ylim([0, 105])
    
    # 2. Success Rate vs Average Return (Scatter)
    scatter = ax2.scatter(sessions_df['SuccessRate'], sessions_df['AvgReturn'],
                         c=sessions_df['Session'], cmap='viridis', s=100, alpha=0.6, edgecolors='black')
    ax2.set_xlabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Average Return', fontsize=12, fontweight='bold')
    ax2.set_title('Success Rate vs Average Return by Session',
                  fontsize=14, fontweight='bold', pad=15)
    plt.colorbar(scatter, ax=ax2, label='Session Number')
    ax2.grid(True, alpha=0.3)
    ax2.axvline(x=50, color='gray', linestyle='--', alpha=0.5)
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "session_success_rates.png"))
    print(f"   [OK] Kaydedildi: session_success_rates.png")
    plt.close()

def plot_all_sessions_termination_reasons(sessions_data):
    """Tüm session'lar boyunca termination reasons pasta grafiği"""
    print("6. All Sessions Termination Reasons grafiği oluşturuluyor...")
    
    # Tüm session'lardan termination reason'ları topla
    all_reasons = []
    for sess in sessions_data:
        df = sess['df']
        all_reasons.extend(df['Reason'].astype(str).str.strip().tolist())
    
    reason_counts = pd.Series(all_reasons).value_counts()
    
    # En çok görülen 10 sebep
    top_n = min(10, len(reason_counts))
    reason_counts_top = reason_counts.head(top_n)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # 1. Pasta Grafiği
    colors = sns.color_palette("Set3", len(reason_counts_top))
    # Success için özel renk (yeşil)
    if 'Success' in reason_counts_top.index:
        success_idx = list(reason_counts_top.index).index('Success')
        colors[success_idx] = '#2ecc71'
    
    wedges, texts, autotexts = ax1.pie(reason_counts_top.values, 
                                       labels=reason_counts_top.index,
                                       autopct='%1.1f%%',
                                       startangle=90,
                                       colors=colors,
                                       textprops={'fontsize': 11})
    
    # Yüzde değerlerini kalın yap
    for autotext in autotexts:
        autotext.set_color('black')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)
    
    ax1.set_title('All Sessions: Termination Reasons Distribution (Pie Chart)',
                  fontsize=14, fontweight='bold', pad=20)
    
    # 2. Bar Chart (daha okunabilir)
    bars = ax2.barh(range(len(reason_counts_top)), reason_counts_top.values,
                    color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
    
    # Success bar'ı vurgula
    if 'Success' in reason_counts_top.index:
        success_idx = list(reason_counts_top.index).index('Success')
        bars[success_idx].set_alpha(1.0)
        bars[success_idx].set_edgecolor('darkgreen')
        bars[success_idx].set_linewidth(2.5)
    
    ax2.set_yticks(range(len(reason_counts_top)))
    ax2.set_yticklabels(reason_counts_top.index)
    ax2.set_xlabel('Episode Count', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Termination Reason', fontsize=12, fontweight='bold')
    ax2.set_title('All Sessions: Termination Reasons Distribution (Bar Chart)',
                  fontsize=14, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3, axis='x')
    
    # Değerleri bar'ların üzerine yaz
    for i, (bar, count) in enumerate(zip(bars, reason_counts_top.values)):
        width = bar.get_width()
        percentage = (count / len(all_reasons)) * 100
        ax2.text(width + len(all_reasons) * 0.01, bar.get_y() + bar.get_height()/2,
                f'{count} ({percentage:.1f}%)',
                ha='left', va='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "all_sessions_termination_reasons.png"))
    print(f"   [OK] Kaydedildi: all_sessions_termination_reasons.png")
    plt.close()

def main():
    print("="*80)
    print("SESSION BAZLI TRAINING ANALİZİ")
    print("="*80)
    print()
    
    # Session dosyalarını yükle
    print("Session dosyaları yükleniyor...")
    sessions_data = load_all_sessions(SESSION_DIR)
    
    if len(sessions_data) == 0:
        print("\n❌ HATA: Session dosyası bulunamadı!")
        return
    
    print(f"✓ {len(sessions_data)} session yüklendi\n")
    
    print("Grafikler oluşturuluyor...")
    print("-"*80)
    
    # Grafikleri oluştur
    plot_curriculum_progression(sessions_data)
    plot_session_performance_timeline(sessions_data)
    plot_landing_quality_analysis(sessions_data)
    plot_start_altitude_progression(sessions_data)
    plot_session_success_rates(sessions_data)
    plot_all_sessions_termination_reasons(sessions_data)
    
    print("-"*80)
    print(f"\n✓ Tüm grafikler oluşturuldu!")
    print(f"📁 Görseller '{OUTPUT_DIR}' klasörüne kaydedildi.")

if __name__ == "__main__":
    main()
