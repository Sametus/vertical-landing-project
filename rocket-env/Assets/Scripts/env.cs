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

        public float mainThrustPower = 10000f;
        public float rcsPower = 1000f;

        private Vector3 feetOffset = new Vector3(0, -2.0f, 0);

        public void ResetEnv(float x, float y, float z, float pitch, float yaw)
        {
            rocketRb.linearVelocity = Vector3.zero;
            rocketRb.angularVelocity = Vector3.zero;

            transform.position = new Vector3(x, y, z);

            transform.rotation = Quaternion.Euler(pitch, yaw, 0f);

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

            // Pitch: X ekseni (transform.right) - öne/arkaya yatma
            // Yaw: Z ekseni (transform.forward) - sağa/sola yatma  
            // Roll: Y ekseni (transform.up) - kendi ekseninde dönme
            Vector3 pitchTork = transform.right * pitch * rcsPower;
            Vector3 yawTork = transform.forward * yaw * rcsPower;
            Vector3 rollTork = transform.up * roll * rcsPower;

            rocketRb.AddTorque(pitchTork + yawTork + rollTork);
        }

        // connector.cs ilet
        public string getStates()
        {
            if (targetPoint == null || rocketRb == null) return "";
            Vector3 globalFeetPos = transform.TransformPoint(feetOffset);

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