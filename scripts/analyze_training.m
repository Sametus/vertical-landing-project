%% Training Log Analizi ve Görselleştirme
% Detaylı eğitim loglarından grafikler oluşturur
% 
% Kullanım: MATLAB'de analyze_training.m dosyasını çalıştırın
% Gereksinimler: Statistics and Machine Learning Toolbox (bazı grafikler için)

clear; clc; close all;

%% Dosya Yolları
models_dir = '../models';
detailed_log_file = fullfile(models_dir, 'detailed_log.csv');
update_log_file = fullfile(models_dir, 'update_logs.csv');
images_dir = '../images';

% Çıktı klasörü oluştur
if ~exist(images_dir, 'dir')
    mkdir(images_dir);
end

fprintf('=== Training Log Analizi ===\n\n');

%% 1. Veri Yükleme
fprintf('Log dosyalari yukleniyor...\n');

if ~exist(detailed_log_file, 'file')
    error('Dosya bulunamadi: %s', detailed_log_file);
end

% Detaylı log
opts = detectImportOptions(detailed_log_file);
detailed_log = readtable(detailed_log_file, opts);
fprintf('✓ %d episode yuklendi\n', height(detailed_log));

% Update log (varsa)
update_log = [];
if exist(update_log_file, 'file')
    opts = detectImportOptions(update_log_file);
    update_log = readtable(update_log_file, opts);
    fprintf('✓ %d update yuklendi\n', height(update_log));
end

fprintf('\nGrafikler olusturuluyor...\n\n');

%% 2. Success Rate Trendi
fprintf('1. Success rate trendi...\n');

success_by_update = groupsummary(detailed_log, 'Update', ...
    'mean', 'Reason', @(x) sum(strcmp(x, 'Success')) / length(x) * 100);

success_by_update = sortrows(success_by_update, 'Update');

% 10-update moving average
window_size = 10;
if height(success_by_update) >= window_size
    ma_success = movmean(success_by_update.mean_Reason, window_size);
else
    ma_success = success_by_update.mean_Reason;
end

figure('Position', [100, 100, 1200, 600]);
plot(success_by_update.Update, success_by_update.mean_Reason, 'o', ...
    'MarkerSize', 4, 'Color', [0.2 0.6 1], 'MarkerFaceColor', [0.2 0.6 1], ...
    'DisplayName', 'Success Rate');
hold on;
plot(success_by_update.Update, ma_success, '-', ...
    'LineWidth', 2.5, 'Color', [1 0.2 0.2], 'DisplayName', '10-Update Moving Average');
xlabel('Update', 'FontSize', 12);
ylabel('Success Rate (%)', 'FontSize', 12);
title('Basari Orani Trendi (Update''e Gore)', 'FontSize', 14, 'FontWeight', 'bold');
grid on;
legend('Location', 'best');
saveas(gcf, fullfile(images_dir, 'success_rate_trend.png'));
fprintf('   ✓ Kaydedildi: success_rate_trend.png\n');
close;

%% 3. Başlangıç İrtifası vs Success
fprintf('2. Baslangic irtifasi vs Success analizi...\n');

% Success durumu
is_success = strcmp(detailed_log.Reason, 'Success');

% İrtifa aralıkları
alt_bins = [0, 3, 6, 10, 15, 20, inf];
alt_labels = {'0-3m', '3-6m', '6-10m', '10-15m', '15-20m', '20m+'};

[~, ~, alt_idx] = histcounts(detailed_log.StartAlt, alt_bins);

% Her aralık için success oranı
alt_ranges = cell(height(detailed_log), 1);
success_rates = zeros(length(alt_labels), 1);
episode_counts = zeros(length(alt_labels), 1);

for i = 1:length(alt_labels)
    idx = (alt_idx == i);
    if any(idx)
        alt_ranges(idx) = {alt_labels{i}};
        success_rates(i) = sum(is_success(idx)) / sum(idx) * 100;
        episode_counts(i) = sum(idx);
    end
end

% Bar chart
valid_idx = episode_counts > 0;
figure('Position', [100, 100, 1200, 600]);
bars = bar(categorical(alt_labels(valid_idx)), success_rates(valid_idx), ...
    'FaceColor', 'flat');
bars.CData = repmat(linspace(0.2, 0.8, sum(valid_idx))', 1, 3);
bars.CData(:, 2) = bars.CData(:, 1);
bars.CData(:, 3) = 1 - bars.CData(:, 1);

% Değerleri üzerine yaz
for i = 1:sum(valid_idx)
    idx = find(valid_idx);
    text(i, success_rates(idx(i)) + 2, ...
        sprintf('%.1f%%\n(%d/%d)', success_rates(idx(i)), ...
        sum(is_success(alt_idx == idx(i))), episode_counts(idx(i))), ...
        'HorizontalAlignment', 'center', 'FontSize', 10);
end

xlabel('Baslangic Irtifa Araligi', 'FontSize', 12);
ylabel('Success Rate (%)', 'FontSize', 12);
title('Baslangic Irtifasina Gore Basari Orani', 'FontSize', 14, 'FontWeight', 'bold');
grid on;
ylim([0, max(success_rates(valid_idx)) * 1.2]);
saveas(gcf, fullfile(images_dir, 'start_altitude_vs_success.png'));
fprintf('   ✓ Kaydedildi: start_altitude_vs_success.png\n');
close;

%% 4. Başlangıç İrtifası Scatter Plot
fprintf('3. Baslangic irtifasi scatter plot...\n');

figure('Position', [100, 100, 1200, 600]);

% Failure points
failure_idx = ~is_success;
scatter(detailed_log.Episode(failure_idx), detailed_log.StartAlt(failure_idx), ...
    15, [1 0.3 0.3], 'filled', 'MarkerFaceAlpha', 0.3, 'DisplayName', 'Failure');
hold on;

% Success points
success_idx = is_success;
scatter(detailed_log.Episode(success_idx), detailed_log.StartAlt(success_idx), ...
    20, [0.2 0.8 0.2], 'filled', 'MarkerFaceAlpha', 0.7, 'DisplayName', 'Success');

xlabel('Episode', 'FontSize', 12);
ylabel('Baslangic Irtifasi (m)', 'FontSize', 12);
title('Baslangic Irtifasi vs Basari (Zaman Serisi)', 'FontSize', 14, 'FontWeight', 'bold');
legend('Location', 'best');
grid on;
saveas(gcf, fullfile(images_dir, 'start_altitude_scatter.png'));
fprintf('   ✓ Kaydedildi: start_altitude_scatter.png\n');
close;

%% 5. Termination Reason Dağılımı
fprintf('4. Termination reason dagilimi...\n');

reason_counts = groupsummary(detailed_log, 'Reason', 'GroupCount');
reason_counts = sortrows(reason_counts, 'GroupCount', 'descend');

% En çok görülen 8 sebep
top_n = min(8, height(reason_counts));
reason_counts = reason_counts(1:top_n, :);

figure('Position', [100, 100, 800, 600]);
pie(reason_counts.GroupCount, reason_counts.Reason);
title('Episode Sonlanma Sebepleri Dagilimi', 'FontSize', 14, 'FontWeight', 'bold');
colormap(parula(top_n));
saveas(gcf, fullfile(images_dir, 'termination_reasons.png'));
fprintf('   ✓ Kaydedildi: termination_reasons.png\n');
close;

%% 6. Loss Trendi (eğer update_log varsa)
if ~isempty(update_log)
    fprintf('5. Loss trendi...\n');
    
    figure('Position', [100, 100, 1200, 700]);
    
    % Subplot 1: Total Loss
    subplot(2, 1, 1);
    plot(update_log.Update, update_log.Loss, '-', 'LineWidth', 1.5, 'Color', [0.2 0.4 1]);
    xlabel('Update', 'FontSize', 11);
    ylabel('Total Loss', 'FontSize', 11);
    title('Total Loss Trendi', 'FontSize', 12, 'FontWeight', 'bold');
    grid on;
    
    % Subplot 2: Policy Loss & Value Loss
    subplot(2, 1, 2);
    plot(update_log.Update, update_log.PolicyLoss, '-', 'LineWidth', 1.5, ...
        'Color', [0.2 0.8 0.2], 'DisplayName', 'Policy Loss');
    hold on;
    plot(update_log.Update, update_log.ValueLoss, '-', 'LineWidth', 1.5, ...
        'Color', [1 0.5 0], 'DisplayName', 'Value Loss');
    xlabel('Update', 'FontSize', 11);
    ylabel('Loss', 'FontSize', 11);
    title('Policy Loss ve Value Loss Trendi', 'FontSize', 12, 'FontWeight', 'bold');
    legend('Location', 'best');
    grid on;
    
    sgtitle('Loss Trendi (Update''e Gore)', 'FontSize', 14, 'FontWeight', 'bold');
    saveas(gcf, fullfile(images_dir, 'loss_trend.png'));
    fprintf('   ✓ Kaydedildi: loss_trend.png\n');
    close;
end

%% 7. Return Dağılımı
fprintf('6. Return dagilimi...\n');

figure('Position', [100, 100, 1200, 600]);

% Histogram edges
return_edges = linspace(min(detailed_log.Return), max(detailed_log.Return), 50);

% Success returns
histogram(detailed_log.Return(is_success), return_edges, ...
    'FaceColor', [0.2 0.8 0.2], 'FaceAlpha', 0.7, 'DisplayName', 'Success');
hold on;

% Failure returns
histogram(detailed_log.Return(failure_idx), return_edges, ...
    'FaceColor', [1 0.3 0.3], 'FaceAlpha', 0.7, 'DisplayName', 'Failure');

xlabel('Return', 'FontSize', 12);
ylabel('Frekans', 'FontSize', 12);
title('Return Dagilimi (Success vs Failure)', 'FontSize', 14, 'FontWeight', 'bold');
legend('Location', 'best');
grid on;
saveas(gcf, fullfile(images_dir, 'return_distribution.png'));
fprintf('   ✓ Kaydedildi: return_distribution.png\n');
close;

%% 8. Özet İstatistikler
fprintf('\n=== Ozet Istatistikler ===\n');
fprintf('Toplam Episode: %d\n', height(detailed_log));
fprintf('Success Orani: %.2f%%\n', sum(is_success) / height(detailed_log) * 100);
fprintf('Ortalama Baslangic Irtifasi: %.2f m\n', mean(detailed_log.StartAlt));
fprintf('Success olanlarin ort. baslangic irtifasi: %.2f m\n', ...
    mean(detailed_log.StartAlt(is_success)));
fprintf('Failure olanlarin ort. baslangic irtifasi: %.2f m\n', ...
    mean(detailed_log.StartAlt(failure_idx)));

fprintf('\n[OK] Tum grafikler olusturuldu!\n');
fprintf('Goruntuler ''%s'' klasorunde kaydedildi.\n', images_dir);

