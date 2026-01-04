using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;
using System.Globalization;

namespace Assets.Scripts
{ 

    public class env: MonoBehaviour
    {

        [Header("Physics & Components")]
        public Rigidbody rocketRb;
        public Transform targetPoint;
        public Transform bottomSensor; // YENI: Sanal nokta - roketin ayak ucu hizasındaki sensör

        [Header("Effects")]
        public ParticleSystem mainEngineParticles;

        public float mainThrustPower = 20000f;  // Düşey itki gücü artırıldı (10000 → 15000)
        public float rcsPower = 1200f;

        // feetOffset artık kullanılmıyor - bottomSensor kullanılıyor
        // private Vector3 feetOffset = new Vector3(0, -2.0f, 0);

        void Start()
        {
            // Kısıtlamaları KALDIRIYORUZ. 
            // Roket tamamen serbest olsun, dengesini yapay zeka sağlasın.
            rocketRb.constraints = RigidbodyConstraints.None; 

            // BottomSensor kontrolü - Unity Editor'da atanmış olmalı
            if (bottomSensor == null)
            {
                Debug.LogWarning("BottomSensor atanmamış! Roket pivot pozisyonu kullanılacak.");
            }
        }

        void FixedUpdate()
        {
            
        }

        public void ResetEnv(float x, float y, float z, float pitch, float yaw)
        {
            rocketRb.linearVelocity = Vector3.zero;
            rocketRb.angularVelocity = Vector3.zero;

            transform.position = new Vector3(x, y, z);
            
            // Başlangıçta düzgün doğsun ama sonra serbest kalsın
            transform.rotation = Quaternion.Euler(pitch, yaw, 0f);
            
            // Kısıtlama yok
            rocketRb.constraints = RigidbodyConstraints.None;

            if (mainEngineParticles != null)
            {
                mainEngineParticles.Stop();
                mainEngineParticles.Clear();
            }

            Debug.Log("........ORTAM SIFIRLANDI..........");
        }

        public void doAction(string dataString)
        {
            dataString = dataString.Replace("[", "").Replace("]", "").Replace(" ", "").Trim();

            if (string.IsNullOrEmpty(dataString)) return;

            string[] parts = dataString.Split(',');

            if (parts.Length < 1) return;

            if (!float.TryParse(parts[0], NumberStyles.Any, CultureInfo.InvariantCulture, out float modeRaw))
            {
                return; // Mod okunamadıysa çık
            }

            int mode = (int)modeRaw;

            switch (mode)
            {
                case 1: // RESET
                    if (parts.Length >= 6)
                    {
                        float x = ParseFloat(parts[1]);
                        float y = ParseFloat(parts[2]);
                        float z = ParseFloat(parts[3]);
                        float pitch = ParseFloat(parts[4]);
                        float yaw = ParseFloat(parts[5]);

                        ResetEnv(x, y, z, pitch, yaw);
                    }
                    break;

                case 0:
                    if (parts.Length >= 5)
                    {
                        float pitch = ParseFloat(parts[1]);
                        float yaw = ParseFloat(parts[2]);
                        float thrust = ParseFloat(parts[3]);
                        float roll = ParseFloat(parts[4]);

                        ApplyPhysics(pitch, yaw, thrust, roll);
                    }
                    break;
            }
        }
        private float ParseFloat(string value)
        {
            if (float.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out float result))
            {
                return result;
            }
            return 0.0f;
        }

        private void ApplyPhysics(float pitch, float yaw, float thrust, float roll)
        {
            float motorGucu = Mathf.Clamp01(thrust);
            rocketRb.AddRelativeForce(Vector3.up * motorGucu * mainThrustPower);

            // UNITY EKSEN EŞLEŞMESİ (DÜZELTİLDİ):
            // Quaternion.Euler(pitch, yaw, roll) sırası:
            //   pitch (X): Öne-arkaya yatma → transform.right (X ekseni) ✓
            //   yaw   (Y): Sağa-sola dönme → transform.up (Y ekseni) ✓
            //   roll  (Z): Kendi ekseninde dönme → transform.forward (Z ekseni) ✓
            // ÖNCEKİ KOD: yaw→forward, roll→up YANLIŞTI! DÜZELTİLDİ.
            
            // ROLL-PITCH COUPLING DÜZELTMESİ:
            // AddRelativeTorque kullanarak roll dönmesinin pitch/yaw torklarına etkisini önlüyoruz
            // AddRelativeTorque local space'de tork uygular ve roll coupling'i otomatik handle eder
            // transform.right/up/forward kullanmalıyız (local space vektörleri)
            Vector3 pitchTork = transform.right * pitch * rcsPower;        // Local X ekseni → Pitch ✓
            Vector3 yawTork   = transform.up * yaw * rcsPower;             // Local Y ekseni → Yaw ✓
            Vector3 rollTork  = transform.forward * roll * (rcsPower * 0.1f); // Local Z ekseni → Roll ✓

            // AddRelativeTorque: Local space'de tork uygular, roll coupling'i Unity otomatik handle eder
            rocketRb.AddRelativeTorque(pitchTork + yawTork + rollTork);

            // Efekt Kodları Aynen Kalabilir
            if (mainEngineParticles != null)
            {
                var emission = mainEngineParticles.emission;
                if (motorGucu > 0.01f)
                {
                    if (!mainEngineParticles.isPlaying) mainEngineParticles.Play();
                    emission.rateOverTime = motorGucu * 500f;
                }
                else
                {
                    emission.rateOverTime = 0f;
                }
            }
        }

        // connector.cs ilet
        public string getStates()
        {
            if (rocketRb == null) return "0,0,0,0,0,0,0,0,0,0,0,0,0";
            
            // YENI MANTIK: feetOffset yerine bottomSensor'ın dünya koordinatını alıyoruz
            // Eğer sensor atanmadıysa roketin kendi pozisyonunu kullanır.
            Vector3 currentBottomPos = (bottomSensor != null) ? bottomSensor.position : transform.position;
            
            Vector3 targetPos = (targetPoint != null) ? targetPoint.position : Vector3.zero;

            // Hedefe olan uzaklığı artık bu sanal noktadan hesaplıyoruz
            float dx = targetPos.x - currentBottomPos.x;
            float dy = currentBottomPos.y - targetPos.y; // Gerçek yerden yükseklik
            float dz = targetPos.z - currentBottomPos.z;
            Vector3 vel = rocketRb.linearVelocity; // Unity 6 standardı
            Vector3 angVel = rocketRb.angularVelocity;
            Quaternion rot = transform.rotation;

            // Python beklenen sıra: dx, dy, dz, vx, vy, vz, wx, wy, wz, qx, qy, qz, qw
            // InvariantCulture kullanarak ondalık ayırıcıyı nokta (.) yapıyoruz
            return string.Format(CultureInfo.InvariantCulture,
                "{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11},{12}",
                dx, dy, dz, vel.x, vel.y, vel.z, angVel.x, angVel.y, angVel.z, rot.x, rot.y, rot.z, rot.w);
        }
    }
}

/*
 * 
 * 
 * public void doAction(string dataString)
        {

            if (string.IsNullOrEmpty(dataString)) return;
 
            string[] parts = dataString.Split(',');
            
            if (parts.Length < 1) return;

            string mod = parts[0].ToLower();

            if (mod == "1")
            {
                if (parts.Length >= 6)
                {
                    float x = float.Parse(parts[1], CultureInfo.InvariantCulture);
                    float y = float.Parse(parts[2], CultureInfo.InvariantCulture);
                    float z = float.Parse(parts[3], CultureInfo.InvariantCulture);
                    float pitch = float.Parse(parts[4], CultureInfo.InvariantCulture);
                    float yaw = float.Parse(parts[5], CultureInfo.InvariantCulture);
                    ResetEnv(x, y, z, pitch, yaw);
                }

                
            }
            else if (mod == "false" || mod == "0")
            {
                if (parts.Length >= 4)
                {
                    float pitchVal = float.Parse(parts[1], CultureInfo.InvariantCulture);
                    float yawVal = float.Parse(parts[2], CultureInfo.InvariantCulture);
                    float thrustVal = float.Parse(parts[3], CultureInfo.InvariantCulture);

                    ApplyPhysics(pitchVal, yawVal, thrustVal);
                }
            }
           
        }
 * 
 * 
 * */