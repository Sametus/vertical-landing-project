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

        public Rigidbody rocketRb;
        public Transform targetPoint;

        [Header("Effects")]
        public ParticleSystem mainEngineParticles;

        public float mainThrustPower = 15000f;  // Düşey itki gücü artırıldı (10000 → 15000)
        public float rcsPower = 1000f;

        private Vector3 feetOffset = new Vector3(0, -2.0f, 0);

        void Start()
        {
            // Kısıtlamaları KALDIRIYORUZ. 
            // Roket tamamen serbest olsun, dengesini yapay zeka sağlasın.
            rocketRb.constraints = RigidbodyConstraints.None; 

            // Otomatik Ayak Mesafesi Hesaplama (Önceki konuşmamızdan)
            Collider col = GetComponent<Collider>();
            if (col != null)
            {
                float halfHeight = col.bounds.extents.y / transform.localScale.y;
                feetOffset = new Vector3(0, -halfHeight, 0);
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

            // EKSENLERİ DOĞRU OTURTMA:
            // transform.right   (X) -> PITCH (Öne arkaya yatma)
            // transform.forward (Z) -> YAW (Sağa sola yatma)
            // transform.up      (Y) -> ROLL (Kendi ekseninde dönme / Spin)
            
            Vector3 pitchTork = transform.right * pitch * rcsPower;
            Vector3 yawTork   = transform.forward * yaw * rcsPower;
            Vector3 rollTork  = transform.up * roll * (rcsPower * 0.1f); // Artık roll çalışıyor

            rocketRb.AddTorque(pitchTork + yawTork + rollTork);

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

        // Ayakların en alt noktasını bulur (açılı ayaklar için)
        private Vector3 FindLowestLegPoint()
        {
            Vector3 lowestPoint = transform.TransformPoint(feetOffset); // Gövdenin alt ucu başlangıç
            
            // Tüm child objeleri kontrol et (ayakları bul)
            foreach (Transform child in transform)
            {
                // Leg veya Leg_Pivot ile başlayan objeleri bul
                if (child.name.Contains("Leg") && !child.name.Contains("Pivot"))
                {
                    Collider legCol = child.GetComponent<Collider>();
                    if (legCol != null)
                    {
                        // Collider'ın en alt noktasını al (bounds.min.y)
                        Vector3 legBottom = legCol.bounds.min;
                        if (legBottom.y < lowestPoint.y)
                        {
                            lowestPoint = legBottom;
                        }
                    }
                    else
                    {
                        // Collider yoksa, transform pozisyonunu kullan
                        // Ama açılı olduğu için yaklaşık hesaplama yapalım
                        Vector3 legPos = child.position;
                        // Ayak uzunluğu yaklaşık olarak scale.y ile verilmiş olabilir
                        float legLength = child.localScale.y;
                        // 30 derece açıyla en alt nokta: sin(30) * legLength = 0.5 * legLength
                        float bottomOffset = legLength * 0.5f;
                        Vector3 legBottom = legPos - Vector3.up * bottomOffset;
                        if (legBottom.y < lowestPoint.y)
                        {
                            lowestPoint = legBottom;
                        }
                    }
                }
            }
            
            return lowestPoint;
        }

        // connector.cs ilet
        public string getStates()
        {
            if (targetPoint == null || rocketRb == null) return "";
            
            // Açılı ayaklar için gerçek en alt noktayı bul
            Vector3 globalFeetPos = FindLowestLegPoint();

            float dx = targetPoint.position.x - globalFeetPos.x;
            float dz = targetPoint.position.z - globalFeetPos.z;
            float dy = globalFeetPos.y - targetPoint.position.y;
            Vector3 velocity = rocketRb.linearVelocity;
            Vector3 angularVel = rocketRb.angularVelocity;

            Quaternion rotation = transform.rotation;

            // Python beklenen sıra: dx, dy, dz, vx, vy, vz, wx, wy, wz, qx, qy, qz, qw
            // InvariantCulture kullanarak ondalık ayırıcıyı nokta (.) yapıyoruz
            string states =
                dx.ToString(CultureInfo.InvariantCulture) + "," +
                dy.ToString(CultureInfo.InvariantCulture) + "," +
                dz.ToString(CultureInfo.InvariantCulture) + "," +
                velocity.x.ToString(CultureInfo.InvariantCulture) + "," +
                velocity.y.ToString(CultureInfo.InvariantCulture) + "," +
                velocity.z.ToString(CultureInfo.InvariantCulture) + "," +
                angularVel.x.ToString(CultureInfo.InvariantCulture) + "," +
                angularVel.y.ToString(CultureInfo.InvariantCulture) + "," +
                angularVel.z.ToString(CultureInfo.InvariantCulture) + "," +
                rotation.x.ToString(CultureInfo.InvariantCulture) + "," +
                rotation.y.ToString(CultureInfo.InvariantCulture) + "," +
                rotation.z.ToString(CultureInfo.InvariantCulture) + "," +
                rotation.w.ToString(CultureInfo.InvariantCulture);

            return  states;
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