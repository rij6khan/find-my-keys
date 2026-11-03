// Copyright (c) Meta Platforms, Inc. and affiliates.

using System.Collections;
using System.Collections.Generic;
using Meta.XR;
using Meta.XR.Samples;
using UnityEngine;
using UnityEngine.Events;

namespace PassthroughCameraSamples.MultiObjectDetection
{
    [MetaCodeSample("PassthroughCameraApiSamples-MultiObjectDetection")]
    public class DetectionManager : MonoBehaviour
    {
        // ============================================================
        // References
        // ============================================================

        [SerializeField]
        private PassthroughCameraAccess m_cameraAccess;

        [Header("Placement configuration")]
        [SerializeField]
        private DetectionSpawnMarkerAnim m_spawnMarker;

        [SerializeField]
        private SentisInferenceUiManager m_uiInference;


        // ============================================================
        // Object Memory
        // ============================================================

        [Header("Object Memory")]
        [SerializeField]
        private QuestObjectSender m_objectSender;


        [Space(10)]
        public UnityEvent<int> OnObjectsIdentified;


        // ============================================================
        // Runtime state
        // ============================================================

        private readonly List<DetectionSpawnMarkerAnim>
            m_spawnedEntities = new();

        private bool m_isStarted;

        internal OVRSpatialAnchor m_spatialAnchor;

        private bool m_isHeadsetTracking;


        // ============================================================
        // Unity lifecycle
        // ============================================================

        private void Awake()
        {
            StartCoroutine(
                UpdateSpatialAnchor()
            );

            OVRManager.TrackingLost +=
                OnTrackingLost;

            OVRManager.TrackingAcquired +=
                OnTrackingAcquired;
        }


        private void OnDestroy()
        {
            EraseSpatialAnchor();

            OVRManager.TrackingLost -=
                OnTrackingLost;

            OVRManager.TrackingAcquired -=
                OnTrackingAcquired;
        }


        private void OnTrackingLost()
        {
            m_isHeadsetTracking = false;
        }


        private void OnTrackingAcquired()
        {
            m_isHeadsetTracking = true;
        }


        // ============================================================
        // Input
        // ============================================================

        private void Update()
        {
            if (!m_isStarted)
            {
                // Wait until passthrough camera is active.
                if (m_cameraAccess.IsPlaying)
                {
                    m_isStarted = true;
                }
            }
            else
            {
                // ----------------------------------------------------
                // A button:
                // 1. Place marker
                // 2. Send real detection to Windows object memory
                // ----------------------------------------------------

                if (
                    InputManager
                        .IsButtonADownOrPinchStarted()
                )
                {
                    SpawnCurrentDetectedObjects();
                }
            }


            // --------------------------------------------------------
            // B button:
            // Clear remembered markers
            // --------------------------------------------------------

            if (
                InputManager
                    .IsButtonBDownOrMiddleFingerPinchStarted()
            )
            {
                CleanMarkers();
            }
        }


        // ============================================================
        // Spatial Anchor
        // ============================================================

        private IEnumerator UpdateSpatialAnchor()
        {
            while (true)
            {
                yield return null;


                if (m_spatialAnchor == null)
                {
                    yield return
                        CreateSpatialAnchorAndSave();


                    if (m_spatialAnchor == null)
                    {
                        continue;
                    }
                }


                if (!m_spatialAnchor.IsTracked)
                {
                    yield return
                        RestoreSpatialAnchorTracking();
                }
            }


            // ========================================================
            // Create and save spatial anchor
            // ========================================================

            IEnumerator CreateSpatialAnchorAndSave()
            {
                m_spatialAnchor =
                    m_uiInference
                        .ContentParent
                        .gameObject
                        .AddComponent<OVRSpatialAnchor>();


                // Wait for localization because SaveAnchorAsync()
                // requires the anchor to be localized first.
                while (true)
                {
                    if (m_spatialAnchor == null)
                    {
                        // Spatial Anchor destroys itself
                        // if creation fails.
                        yield break;
                    }


                    if (m_spatialAnchor.Localized)
                    {
                        break;
                    }


                    yield return null;
                }


                // Save anchor.
                var awaiter =
                    m_spatialAnchor
                        .SaveAnchorAsync()
                        .GetAwaiter();


                while (!awaiter.IsCompleted)
                {
                    yield return null;
                }


                var saveAnchorResult =
                    awaiter.GetResult();


                if (!saveAnchorResult.Success)
                {
                    LogSpatialAnchor(
                        $"SaveAnchorAsync() failed " +
                        $"{saveAnchorResult}",
                        LogType.Error
                    );


                    EraseSpatialAnchor();

                    yield break;
                }


                LogSpatialAnchor(
                    "created"
                );
            }


            // ========================================================
            // Restore anchor tracking
            // ========================================================

            IEnumerator RestoreSpatialAnchorTracking()
            {
                LogSpatialAnchor(
                    "tracking was lost, restoring..."
                );


                const int numRetries = 20;


                for (
                    int i = 0;
                    i < numRetries;
                    i++
                )
                {
                    yield return
                        new WaitForSeconds(1f);


                    if (!m_isHeadsetTracking)
                    {
                        LogSpatialAnchor(
                            $"{nameof(m_isHeadsetTracking)} " +
                            $"is false, retrying ({i})"
                        );

                        continue;
                    }


                    var unboundAnchors =
                        new List<
                            OVRSpatialAnchor.UnboundAnchor
                        >(1);


                    var awaiter =
                        OVRSpatialAnchor
                            .LoadUnboundAnchorsAsync(
                                new[]
                                {
                                    m_spatialAnchor.Uuid
                                },
                                unboundAnchors
                            )
                            .GetAwaiter();


                    while (!awaiter.IsCompleted)
                    {
                        yield return null;
                    }


                    var loadResult =
                        awaiter.GetResult();


                    if (!loadResult.Success)
                    {
                        LogSpatialAnchor(
                            "LoadUnboundAnchorsAsync() " +
                            $"failed {loadResult.Status}, " +
                            $"retrying ({i})",
                            LogType.Error
                        );

                        continue;
                    }


                    if (unboundAnchors.Count != 0)
                    {
                        LogSpatialAnchor(
                            "LoadUnboundAnchorsAsync() " +
                            $"unexpected count:" +
                            $"{unboundAnchors.Count}, " +
                            $"retrying ({i})",
                            LogType.Error
                        );

                        continue;
                    }


                    yield return null;


                    if (!m_spatialAnchor.IsTracked)
                    {
                        LogSpatialAnchor(
                            "tracking is not restored, " +
                            $"retrying ({i})"
                        );

                        continue;
                    }


                    LogSpatialAnchor(
                        "tracking was restored successfully"
                    );


                    yield break;
                }


                LogSpatialAnchor(
                    "tracking restoration failed " +
                    $"after {numRetries} retries",
                    LogType.Warning
                );


                EraseSpatialAnchor();
            }
        }


        // ============================================================
        // Erase Spatial Anchor
        // ============================================================

        private void EraseSpatialAnchor()
        {
            if (m_spatialAnchor != null)
            {
                LogSpatialAnchor(
                    "EraseSpatialAnchor"
                );


                m_spatialAnchor
                    .EraseAnchorAsync();


                DestroyImmediate(
                    m_spatialAnchor
                );


                m_spatialAnchor = null;


                CleanMarkers();


                m_uiInference
                    .ClearAnnotations();
            }
        }


        // ============================================================
        // Clean Markers
        // ============================================================

        private void CleanMarkers()
        {
            LogSpatialAnchor(
                "CleanMarkers"
            );


            foreach (
                var entity
                in m_spawnedEntities
            )
            {
                Destroy(
                    entity.gameObject
                );
            }


            m_spawnedEntities.Clear();


            OnObjectsIdentified?.Invoke(
                -1
            );
        }


        // ============================================================
        // Logging helper
        // ============================================================

        private static void LogSpatialAnchor(
            string message,
            LogType logType = LogType.Log
        )
        {
            Debug.unityLogger.Log(
                logType,
                $"{nameof(OVRSpatialAnchor)}: " +
                $"{message}"
            );
        }


        // ============================================================
        // Spawn markers + create object memory
        // ============================================================

        /// <summary>
        /// Creates a 3D marker for each newly detected object.
        ///
        /// When a marker is created, the object's cleaned class label,
        /// confidence, and Quest-world 3D position are sent to the
        /// Windows Object Memory Server.
        /// </summary>

        private void SpawnCurrentDetectedObjects()
        {
            var newCount = 0;


            foreach (
                SentisInferenceUiManager.BoundingBoxData box
                in m_uiInference.m_boxDrawn
            )
            {
                // ----------------------------------------------------
                // Clean YOLO class label
                // ----------------------------------------------------

                string cleanLabel =
                    box.ClassName?.Trim();


                if (
                    string.IsNullOrWhiteSpace(
                        cleanLabel
                    )
                )
                {
                    Debug.LogWarning(
                        "DETECTION_SKIPPED: " +
                        "YOLO class label is empty."
                    );

                    continue;
                }


                // ----------------------------------------------------
                // Avoid creating duplicate marker/memory
                // ----------------------------------------------------

                if (
                    HasExistingMarkerInBoundingBox(
                        box,
                        cleanLabel
                    )
                )
                {
                    continue;
                }


                // ----------------------------------------------------
                // Real Quest-world 3D object position
                // ----------------------------------------------------

                Vector3 objectPosition =
                    box.BoxRectTransform.position;


                LogSpatialAnchor(
                    $"spawn marker {cleanLabel}"
                );


                // ----------------------------------------------------
                // Create persistent Quest marker
                // ----------------------------------------------------

                var marker =
                    Instantiate(
                        m_spawnMarker,
                        objectPosition,
                        box.BoxRectTransform.rotation,
                        m_uiInference.ContentParent
                    );


                marker.SetYoloClassName(
                    cleanLabel
                );


                m_spawnedEntities.Add(
                    marker
                );


                newCount++;


                // ----------------------------------------------------
                // Send REAL observation to Windows memory server
                // ----------------------------------------------------

                if (m_objectSender != null)
                {
                    Debug.Log(
                        "SEND_DETECTED_OBJECT: " +
                        $"Class=[{cleanLabel}], " +
                        $"Confidence={box.Confidence:F3}, " +
                        $"QuestXYZ=(" +
                        $"{objectPosition.x:F3}, " +
                        $"{objectPosition.y:F3}, " +
                        $"{objectPosition.z:F3})"
                    );


                    // SendObservation now returns the generated
                    // observation ID.
                    string observationId =
                        m_objectSender.SendObservation(
                            cleanLabel,
                            box.Confidence,
                            objectPosition
                        );


                    if (
                        !string.IsNullOrEmpty(
                            observationId
                        )
                    )
                    {
                        Debug.Log(
                            "OBJECT_MEMORY_CREATED: " +
                            $"ID={observationId}, " +
                            $"Class=[{cleanLabel}]"
                        );
                    }
                    else
                    {
                        Debug.LogError(
                            "OBJECT_MEMORY_FAILED: " +
                            $"Class=[{cleanLabel}]"
                        );
                    }
                }
                else
                {
                    Debug.LogWarning(
                        "QuestObjectSender is not assigned " +
                        "in DetectionManager Inspector."
                    );
                }
            }


            OnObjectsIdentified?.Invoke(
                newCount
            );
        }


        // ============================================================
        // Check if marker already exists in current bounding box
        // ============================================================

        private bool HasExistingMarkerInBoundingBox(
            SentisInferenceUiManager.BoundingBoxData box,
            string cleanLabel
        )
        {
            foreach (
                var marker
                in m_spawnedEntities
            )
            {
                // Clean the stored marker label too,
                // so hidden whitespace can never affect comparison.
                string markerLabel =
                    marker
                        .GetYoloClassName()
                        ?.Trim();


                if (
                    markerLabel !=
                    cleanLabel
                )
                {
                    continue;
                }


                var markerWorldPos =
                    marker.transform.position;


                Vector2 localPos =
                    box.BoxRectTransform
                        .InverseTransformPoint(
                            markerWorldPos
                        );


                var sizeDelta =
                    box.BoxRectTransform
                        .sizeDelta;


                var currentBox =
                    new Rect(
                        -sizeDelta.x * 0.5f,
                        -sizeDelta.y * 0.5f,
                        sizeDelta.x,
                        sizeDelta.y
                    );


                if (
                    currentBox.Contains(
                        localPos
                    )
                )
                {
                    return true;
                }
            }


            return false;
        }
    }
}