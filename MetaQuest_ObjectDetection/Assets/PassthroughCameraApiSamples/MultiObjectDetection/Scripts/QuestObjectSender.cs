using System;
using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

namespace PassthroughCameraSamples.MultiObjectDetection
{
    public class QuestObjectSender : MonoBehaviour
    {
        // ============================================================
        // Windows Object Memory Server
        // ============================================================

        [Header("Windows Object Memory Server")]
        [SerializeField]
        private string memoryServerBaseUrl =
            "http://172.25.230.76:8000";


        // ============================================================
        // JSON data structure sent to FastAPI
        // ============================================================

        [Serializable]
        public class QuestObjectObservation
        {
            public string observation_id;
            public string label;
            public float confidence;
            public string timestamp;

            public float quest_x;
            public float quest_y;
            public float quest_z;
        }


        // ============================================================
        // Send detected object metadata
        // ============================================================

        /// <summary>
        /// Sends one detected object observation to the
        /// Windows Object Memory Server.
        ///
        /// Returns the generated observation ID so the same ID
        /// can later be reused for:
        /// - full Quest image
        /// - object crop
        /// - YOR-world coordinates
        /// </summary>
        public string SendObservation(
            string label,
            float confidence,
            Vector3 questPosition)
        {
            // --------------------------------------------------------
            // Clean YOLO class label
            // --------------------------------------------------------

            if (string.IsNullOrWhiteSpace(label))
            {
                Debug.LogError(
                    "QUEST_MEMORY_ERROR: " +
                    "Cannot send object because label is empty."
                );

                return null;
            }


            // Important:
            // removes hidden characters such as \r, \n, and spaces.
            string cleanLabel =
                label.Trim();


            // --------------------------------------------------------
            // Generate ONE observation ID
            // --------------------------------------------------------

            string observationId =
                Guid.NewGuid().ToString("N");


            // --------------------------------------------------------
            // Build observation
            // --------------------------------------------------------

            QuestObjectObservation observation =
                new QuestObjectObservation
                {
                    observation_id =
                        observationId,

                    label =
                        cleanLabel,

                    confidence =
                        confidence,

                    timestamp =
                        DateTime.UtcNow.ToString("o"),

                    quest_x =
                        questPosition.x,

                    quest_y =
                        questPosition.y,

                    quest_z =
                        questPosition.z
                };


            // --------------------------------------------------------
            // Convert to JSON
            // --------------------------------------------------------

            string json =
                JsonUtility.ToJson(
                    observation
                );


            // --------------------------------------------------------
            // Debug output
            // --------------------------------------------------------

            Debug.Log(
                "QUEST_MEMORY_OBJECT: " +
                $"ID={observationId}, " +
                $"Class=[{cleanLabel}], " +
                $"Confidence={confidence:F3}, " +
                $"QuestXYZ=(" +
                $"{questPosition.x:F3}, " +
                $"{questPosition.y:F3}, " +
                $"{questPosition.z:F3})"
            );


            Debug.Log(
                $"QUEST_MEMORY_JSON: {json}"
            );


            // --------------------------------------------------------
            // Send to Windows FastAPI server
            // --------------------------------------------------------

            StartCoroutine(
                SendToMemoryServer(
                    json,
                    observationId
                )
            );


            // This ID will later be reused for image upload.
            return observationId;
        }


        // ============================================================
        // HTTP POST
        // ============================================================

        private IEnumerator SendToMemoryServer(
            string json,
            string observationId)
        {
            // Remove trailing slash if one exists.
            string baseUrl =
                memoryServerBaseUrl.TrimEnd('/');


            string url =
                baseUrl + "/objects";


            Debug.Log(
                "MEMORY_SEND_START: " +
                $"ID={observationId}, " +
                $"URL={url}"
            );


            using (
                UnityWebRequest request =
                    UnityWebRequest.Post(
                        url,
                        json,
                        "application/json"
                    )
            )
            {
                request.timeout = 5;


                yield return
                    request.SendWebRequest();


                // ----------------------------------------------------
                // Success
                // ----------------------------------------------------

                if (
                    request.result ==
                    UnityWebRequest.Result.Success
                )
                {
                    Debug.Log(
                        "MEMORY_SEND_OK: " +
                        $"ID={observationId}, " +
                        $"HTTP={request.responseCode}, " +
                        $"Response=" +
                        $"{request.downloadHandler.text}"
                    );
                }

                // ----------------------------------------------------
                // Failure
                // ----------------------------------------------------

                else
                {
                    Debug.LogError(
                        "MEMORY_SEND_FAILED: " +
                        $"ID={observationId}, " +
                        $"Result={request.result}, " +
                        $"HTTP={request.responseCode}, " +
                        $"Error={request.error}, " +
                        $"Response=" +
                        $"{request.downloadHandler.text}"
                    );
                }
            }
        }
    }
}