using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using UnityEditor.Experimental.GraphView;
using UnityEngine;
using Unity.VisualScripting;

namespace Assets.Scripts
{
    internal class connector : MonoBehaviour
    {
        public env envScript;

        public int port = 5000;
        public string ip = "127.0.0.1";

        private TcpListener server;
        public TcpClient client;
        private Thread serverThread;

        private string gelenMesaj = "";
        private string gonderilecekDurum = "";

        private bool mesajVar = false;   
        private bool unityIsiBitirdi = false; 

        void Start()
        {
            Physics.simulationMode = SimulationMode.Script;

            serverThread = new Thread(StartServerLoop);
            serverThread.IsBackground = true;
            serverThread.Start();
        }

        void StartServerLoop()
        {
            server = new TcpListener(IPAddress.Parse(ip), port);
            server.Start();
            Debug.Log("Server is open, waiting python...");

            client = server.AcceptTcpClient();
            Debug.Log("Python connected");
            NetworkStream stream = client.GetStream();
            byte[] buffer = new byte[1024];
            StringBuilder messageBuilder = new StringBuilder();

            while (client.Connected)
            {
                int bytesRead = stream.Read(buffer, 0, buffer.Length);
                if (bytesRead == 0) break; 

                string receivedData = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                messageBuilder.Append(receivedData);

                // Newline karakterine göre mesajları ayır
                string allData = messageBuilder.ToString();
                int newlineIndex = allData.IndexOf('\n');
                
                if (newlineIndex >= 0)
                {
                    // Newline'a kadar olan kısmı al
                    string message = allData.Substring(0, newlineIndex).Trim();
                    
                    // Kalan kısmı buffer'da tut
                    if (newlineIndex + 1 < allData.Length)
                    {
                        messageBuilder = new StringBuilder(allData.Substring(newlineIndex + 1));
                    }
                    else
                    {
                        messageBuilder.Clear();
                    }

                    gelenMesaj = message;
                    
                    unityIsiBitirdi = false; 
                    mesajVar = true;

                    while (!unityIsiBitirdi && client.Connected)
                    {
                        Thread.Sleep(1); 
                    }
                    byte[] sendMsg = Encoding.UTF8.GetBytes(gonderilecekDurum);
                    stream.Write(sendMsg, 0, sendMsg.Length);
                }
            }
            if (server != null) server.Stop();

        }

        void Update()
        {
            if (mesajVar)
            {
                envScript.doAction(gelenMesaj);
                Physics.Simulate(Time.fixedDeltaTime);
                gonderilecekDurum = envScript.getStates();

                mesajVar = false;
                unityIsiBitirdi=true;
            }
        }


        void OnApplicationQuit()
        {
            Physics.simulationMode = SimulationMode.FixedUpdate;
            if (server != null) server.Stop();
            if (serverThread != null) serverThread.Abort();
        }

    }
}
