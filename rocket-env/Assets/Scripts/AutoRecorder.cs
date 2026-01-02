#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.Recorder;
using UnityEditor.Recorder.Input;
using UnityEditor.Recorder.Encoder; // Encoder ayarları için gerekli
#endif
using UnityEngine;
using System.IO;

public class AutoRecorder : MonoBehaviour
{
#if UNITY_EDITOR
    private RecorderController m_RecorderController;

    [Header("Kayıt Ayarları")]
    public string folderName = "Recordings";
    public bool startOnPlay = true;
    public int frameRate = 30;

    void Start()
    {
        if (startOnPlay)
        {
            StartRecording();
        }
    }

    public void StartRecording()
    {
        var controllerSettings = ScriptableObject.CreateInstance<RecorderControllerSettings>();
        m_RecorderController = new RecorderController(controllerSettings);

        var mediaSettings = ScriptableObject.CreateInstance<MovieRecorderSettings>();
        mediaSettings.name = "My MP4 Recorder";
        mediaSettings.Enabled = true;

        // --- DÜZELTİLMİŞ KISIM (v5.1.3 Uyumlu) ---
        // Artık 'VideoCodec' veya 'ContainerFormat' yok. 
        // Sadece 'OutputCodec' var ve 'MP4' seçince H.264 kullanıyor.
        var encoderSettings = new CoreEncoderSettings
        {
            EncodingQuality = CoreEncoderSettings.VideoEncodingQuality.Medium,
            Codec = CoreEncoderSettings.OutputCodec.MP4
        };
        mediaSettings.EncoderSettings = encoderSettings;

        // Dosya ismi ayarı
        string timestamp = System.DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");
        mediaSettings.OutputFile = Path.Combine(folderName, $"Run_{timestamp}");

        // Ekran ayarı
        var imageSettings = new GameViewInputSettings
        {
            OutputWidth = 1280,
            OutputHeight = 720
        };
        mediaSettings.ImageInputSettings = imageSettings;

        mediaSettings.AudioInputSettings.PreserveAudio = false;

        controllerSettings.AddRecorderSettings(mediaSettings);

        // --- OPTİMİZASYON 3: PLAYBACK HIZI ---
        // Constant yerine Variable yaparsak Unity kasmaya çalışmaz, akışına bırakır.
        // Ama eğitim için Constant (Manual) daha güvenlidir, kasma normaldir.
        controllerSettings.SetRecordModeToManual();
        controllerSettings.FrameRate = frameRate;

        RecorderOptions.VerboseMode = false;
        m_RecorderController.PrepareRecording();
        m_RecorderController.StartRecording();

        Debug.Log($"🎥 OTOMATİK KAYIT (720p) BAŞLADI: {mediaSettings.OutputFile}.mp4");
    }

    void OnDisable()
    {
        if (m_RecorderController != null && m_RecorderController.IsRecording())
        {
            m_RecorderController.StopRecording();
            Debug.Log("💾 VİDEO KAYDEDİLDİ.");
        }
    }
#endif
}