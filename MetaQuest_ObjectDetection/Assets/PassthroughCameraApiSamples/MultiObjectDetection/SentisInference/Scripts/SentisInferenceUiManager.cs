// Copyright (c) Meta Platforms, Inc. and affiliates.

using System.Collections.Generic;
using Meta.XR;
using Meta.XR.Samples;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace PassthroughCameraSamples.MultiObjectDetection
{
    [MetaCodeSample("PassthroughCameraApiSamples-MultiObjectDetection")]
    public class SentisInferenceUiManager : MonoBehaviour
    {
        [Header("Placement configuration")]
        [SerializeField] private EnvironmentRayCastSampleManager m_environmentRaycast;
        [SerializeField] private PassthroughCameraAccess m_cameraAccess;

        [SerializeField] private RectTransform m_detectionBoxPrefab;

        [Space(10)]
        public UnityEvent<int> OnObjectsDetected;

        internal readonly List<BoundingBoxData> m_boxDrawn = new();

        private string[] m_labels;
        private readonly List<BoundingBoxData> m_boxPool = new();

        internal class BoundingBoxData
        {
            public string ClassName;
            public int ClassId;

            // Added: YOLO confidence score for this detection.
            public float Confidence;

            public RectTransform BoxRectTransform;
            public float lastUpdateTime;
        }

        private void Awake()
        {
            m_detectionBoxPrefab.gameObject.SetActive(false);
        }

        private void Update()
        {
            // Remove boxes that have not been updated recently.
            for (int i = m_boxDrawn.Count - 1; i >= 0; i--)
            {
                var box = m_boxDrawn[i];

                const float timeToPersistBoxes = 3f;

                if (Time.time - box.lastUpdateTime > timeToPersistBoxes)
                {
                    ReturnToPool(box);
                    m_boxDrawn.RemoveAt(i);
                }
            }
        }

        public void SetLabels(TextAsset labelsAsset)
        {
            // Parse YOLO class labels.
            m_labels = labelsAsset.text.Split('\n');
        }

        public void DrawUIBoxes(
            List<(int classId, float confidence, Vector4 boundingBox)> detections,
            Vector2 inputSize,
            Pose cameraPose)
        {
            Vector2 currentResolution = m_cameraAccess.CurrentResolution;

            if (detections.Count == 0)
            {
                OnObjectsDetected?.Invoke(0);
                return;
            }

            OnObjectsDetected?.Invoke(detections.Count);

            // Draw the bounding boxes.
            for (int i = 0; i < detections.Count; i++)
            {
                var detection = detections[i];

                float x1 = detection.boundingBox[0];
                float y1 = detection.boundingBox[1];
                float x2 = detection.boundingBox[2];
                float y2 = detection.boundingBox[3];

                Rect rect = new Rect(
                    x1,
                    y1,
                    x2 - x1,
                    y2 - y1
                );

                // Detection center in normalized model coordinates.
                Vector2 normalizedCenter =
                    rect.center / inputSize;

                // Detection center relative to camera-image center.
                Vector2 center =
                    currentResolution *
                    (normalizedCenter - Vector2.one * 0.5f);

                // Get YOLO class name.
                string classname =
                    m_labels[detection.classId]
                    .Replace(" ", "_");

                // ---------------------------------------------------------
                // Convert 2D detection center into a camera ray.
                // ---------------------------------------------------------
                var ray =
                    m_cameraAccess.ViewportPointToRay(
                        new Vector2(
                            normalizedCenter.x,
                            1.0f - normalizedCenter.y
                        ),
                        cameraPose
                    );

                // ---------------------------------------------------------
                // Use environment depth to obtain the physical 3D point.
                // ---------------------------------------------------------
                var worldPos =
                    m_environmentRaycast.Raycast(ray);

                if (!worldPos.HasValue)
                {
                    Debug.Log(
                        $"RaycastManager failed, ray:{ray}, cameraPose:{cameraPose}"
                    );

                    continue;
                }

                var normRect = new Rect(
                    rect.x / inputSize.x,
                    1f - rect.yMax / inputSize.y,
                    rect.width / inputSize.x,
                    rect.height / inputSize.y
                );

                // Distance from Quest camera to detected physical surface.
                float distance =
                    Vector3.Distance(
                        cameraPose.position,
                        worldPos.Value
                    );

                // ---------------------------------------------------------
                // Quest / Unity world-space center of the detected object.
                //
                // We will expose X, Y, Z from this value in the next step.
                // ---------------------------------------------------------
                Vector3 worldSpaceCenter =
                    m_cameraAccess
                    .ViewportPointToRay(
                        normRect.center,
                        cameraPose
                    )
                    .GetPoint(distance);

                Vector3 normal =
                    (worldSpaceCenter - cameraPose.position)
                    .normalized;

                // ---------------------------------------------------------
                // Estimate physical bounding-box size at object depth.
                // ---------------------------------------------------------
                var plane =
                    new Plane(
                        normal,
                        worldSpaceCenter
                    );

                var minRay =
                    m_cameraAccess.ViewportPointToRay(
                        normRect.min,
                        cameraPose
                    );

                var maxRay =
                    m_cameraAccess.ViewportPointToRay(
                        normRect.max,
                        cameraPose
                    );

                plane.Raycast(
                    minRay,
                    out float intersectionDistanceMin
                );

                plane.Raycast(
                    maxRay,
                    out float intersectionDistanceMax
                );

                Vector3 min =
                    minRay.GetPoint(
                        intersectionDistanceMin
                    );

                Vector3 max =
                    maxRay.GetPoint(
                        intersectionDistanceMax
                    );

                // Convert the world-space corners into camera-local space.
                Vector3 topLeftLocal =
                    Quaternion.Inverse(cameraPose.rotation) *
                    (min - cameraPose.position);

                Vector3 bottomRightLocal =
                    Quaternion.Inverse(cameraPose.rotation) *
                    (max - cameraPose.position);

                Vector2 size =
                    new Vector2(
                        Mathf.Abs(
                            bottomRightLocal.x -
                            topLeftLocal.x
                        ),
                        Mathf.Abs(
                            bottomRightLocal.y -
                            topLeftLocal.y
                        )
                    );

                // Create or reuse the green detection box.
                BoundingBoxData boxData =
                    GetOrCreateBoundingBoxData(
                        detection.classId,
                        worldSpaceCenter,
                        size
                    );

                // Store current confidence.
                boxData.Confidence =
                    detection.confidence;

                RectTransform boxRectTransform =
                    boxData.BoxRectTransform;

                // ---------------------------------------------------------
                // Display class + confidence + center information.
                //
                // P1 converts:
                // 0.914 -> 91.4%
                // ---------------------------------------------------------
                boxRectTransform
                    .GetComponentInChildren<Text>()
                    .text =
                    $"Id: {detection.classId}  " +
                    $"Class: {classname}  " +
                    $"Confidence: {detection.confidence:P1}\n" +
                    $"Center (px): {center:0.0}  " +
                    $"Center (%): {normalizedCenter:0.00}";

                // Position the green box in physical world space.
                boxRectTransform.SetPositionAndRotation(
                    worldSpaceCenter,
                    Quaternion.LookRotation(normal)
                );

                boxRectTransform.sizeDelta =
                    size;

                boxData.lastUpdateTime =
                    Time.time;
            }
        }

        private BoundingBoxData GetOrCreateBoundingBoxData(
            int classId,
            Vector3 worldSpaceCenter,
            Vector2 worldSpaceSize)
        {
            BoundingBoxData reusedBox = null;

            for (int i = m_boxDrawn.Count - 1; i >= 0; i--)
            {
                BoundingBoxData box =
                    m_boxDrawn[i];

                Vector3 localPos =
                    box.BoxRectTransform
                    .InverseTransformPoint(
                        worldSpaceCenter
                    );

                Vector4 newBox =
                    new Vector4(
                        localPos.x - worldSpaceSize.x * 0.5f,
                        localPos.y - worldSpaceSize.y * 0.5f,
                        localPos.x + worldSpaceSize.x * 0.5f,
                        localPos.y + worldSpaceSize.y * 0.5f
                    );

                Vector2 sizeDelta =
                    box.BoxRectTransform.sizeDelta;

                Vector4 currentBox =
                    new Vector4(
                        -sizeDelta.x * 0.5f,
                        -sizeDelta.y * 0.5f,
                        sizeDelta.x * 0.5f,
                        sizeDelta.y * 0.5f
                    );

                if (box.ClassId == classId)
                {
                    // Same class:
                    // reuse an overlapping detection box.
                    if (
                        SentisInferenceRunManager.CalculateIoU(
                            newBox,
                            currentBox
                        ) > 0f
                    )
                    {
                        if (reusedBox == null)
                        {
                            reusedBox = box;
                        }
                        else
                        {
                            ReturnToPool(box);
                            m_boxDrawn.RemoveAt(i);
                        }
                    }
                }
                else if (
                    SentisInferenceRunManager.CalculateIoU(
                        newBox,
                        currentBox
                    ) > 0.1f
                )
                {
                    // Different overlapping class:
                    // remove the previous box.
                    ReturnToPool(box);
                    m_boxDrawn.RemoveAt(i);
                }
            }

            if (reusedBox != null)
            {
                return reusedBox;
            }

            // Create a new detection box.
            BoundingBoxData newData =
                GetBoxFromPoolOrCreate();

            newData.ClassId =
                classId;

            newData.ClassName =
                m_labels[classId]
                .Replace(" ", "_");

            m_boxDrawn.Add(
                newData
            );

            return newData;
        }

        private BoundingBoxData GetBoxFromPoolOrCreate()
        {
            if (m_boxPool.Count > 0)
            {
                BoundingBoxData pooled =
                    m_boxPool[
                        m_boxPool.Count - 1
                    ];

                pooled
                    .BoxRectTransform
                    .gameObject
                    .SetActive(true);

                m_boxPool.RemoveAt(
                    m_boxPool.Count - 1
                );

                return pooled;
            }

            RectTransform boxRectTransform =
                Instantiate(
                    m_detectionBoxPrefab,
                    ContentParent
                );

            boxRectTransform
                .gameObject
                .SetActive(true);

            return new BoundingBoxData
            {
                BoxRectTransform =
                    boxRectTransform
            };
        }

        internal Transform ContentParent =>
            m_detectionBoxPrefab.parent;

        private void ReturnToPool(
            BoundingBoxData box)
        {
            box
                .BoxRectTransform
                .gameObject
                .SetActive(false);

            m_boxPool.Add(
                box
            );
        }

        internal void ClearAnnotations()
        {
            foreach (BoundingBoxData box in m_boxDrawn)
            {
                ReturnToPool(box);
            }

            m_boxDrawn.Clear();
        }
    }
}