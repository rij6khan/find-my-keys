using System;
using System.Collections;
using System.IO;
using Meta.XR;
using UnityEngine;

public class QuestAprilTagCapture : MonoBehaviour
{
    private const string LOG = "APRIL_CAPTURE:";

    [SerializeField]
    private PassthroughCameraAccess cameraAccess;

    [Header("AprilTag Configuration")]
    [SerializeField]
    private string tagFamily = "tag36h11";

    [SerializeField]
    private int tagId = 2;

    [SerializeField]
    private float tagSizeMeters = 0.165f;

    private Texture2D snapshotTexture;
    private int captureIndex = 0;
    private bool isCapturing = false;

    // ============================================================
    // Serializable helper classes
    // ============================================================

    [Serializable]
    private class Vector3Data
    {
        public float x;
        public float y;
        public float z;

        public Vector3Data(Vector3 value)
        {
            x = value.x;
            y = value.y;
            z = value.z;
        }
    }

    [Serializable]
    private class QuaternionData
    {
        public float x;
        public float y;
        public float z;
        public float w;

        public QuaternionData(Quaternion value)
        {
            x = value.x;
            y = value.y;
            z = value.z;
            w = value.w;
        }
    }

    [Serializable]
    private class CaptureMetadata
    {
        // --------------------------------------------------------
        // Frame identification
        // --------------------------------------------------------

        public string frame_id;
        public string camera;
        public string timestamp;

        // --------------------------------------------------------
        // Resolution information
        // --------------------------------------------------------

        public int requested_width;
        public int requested_height;

        public int current_width;
        public int current_height;

        public int texture_width;
        public int texture_height;

        public int sensor_width;
        public int sensor_height;

        // --------------------------------------------------------
        // Crop from sensor coordinates to saved image coordinates
        // --------------------------------------------------------

        public float crop_x;
        public float crop_y;

        // --------------------------------------------------------
        // Raw Meta sensor-space intrinsics
        // --------------------------------------------------------

        public float sensor_fx;
        public float sensor_fy;
        public float sensor_cx;
        public float sensor_cy;

        // --------------------------------------------------------
        // Intrinsics corresponding to saved PNG
        // --------------------------------------------------------

        public float image_fx;
        public float image_fy;
        public float image_cx;
        public float image_cy;

        // --------------------------------------------------------
        // Dynamic camera pose in Unity world
        // --------------------------------------------------------

        public Vector3Data camera_world_position;
        public QuaternionData camera_world_quaternion;

        // --------------------------------------------------------
        // Static camera sensor pose relative to headset
        // --------------------------------------------------------

        public Vector3Data camera_relative_to_headset_position;
        public QuaternionData camera_relative_to_headset_quaternion;

        // --------------------------------------------------------
        // Coordinate-frame documentation
        // --------------------------------------------------------

        public string coordinate_system;
        public string intrinsics_mapping;

        // --------------------------------------------------------
        // AprilTag information
        // --------------------------------------------------------

        public string tag_family;
        public int tag_id;
        public float tag_size_m;
    }

    // ============================================================
    // Startup
    // ============================================================

    private IEnumerator Start()
    {
        Debug.Log($"{LOG} Start entered.");

        // If the Inspector reference was lost, try to find
        // PassthroughCameraAccess on this same GameObject.
        if (cameraAccess == null)
        {
            cameraAccess =
                GetComponent<PassthroughCameraAccess>();

            if (cameraAccess != null)
            {
                Debug.Log(
                    $"{LOG} Camera reference found automatically.");
            }
        }

        if (cameraAccess == null)
        {
            Debug.LogError(
                $"{LOG} ERROR: PassthroughCameraAccess is missing.");

            yield break;
        }

        Debug.Log(
            $"{LOG} Camera = {cameraAccess.CameraPosition}");

        Debug.Log(
            $"{LOG} RequestedResolution = " +
            $"{cameraAccess.RequestedResolution.x} x " +
            $"{cameraAccess.RequestedResolution.y}");

        Debug.Log(
            $"{LOG} Waiting for camera stream...");

        while (!cameraAccess.IsPlaying)
        {
            yield return null;
        }

        Debug.Log(
            $"{LOG} Camera IsPlaying = TRUE.");

        PrintCameraInformation();

        Debug.Log(
            $"{LOG} READY - look at AprilTag and press X.");
    }

    // ============================================================
    // Input
    // ============================================================

    private void Update()
    {
        if (!isCapturing &&
            OVRInput.GetDown(OVRInput.RawButton.X))
        {
            StartCoroutine(CaptureFrame());
        }
    }

    // ============================================================
    // Print current calibration information
    // ============================================================

    private void PrintCameraInformation()
    {
        var intrinsics =
            cameraAccess.Intrinsics;

        Vector2Int requested =
            cameraAccess.RequestedResolution;

        Vector2Int current =
            cameraAccess.CurrentResolution;

        Texture texture =
            cameraAccess.GetTexture();

        Debug.Log(
            $"{LOG} RequestedResolution = " +
            $"{requested.x} x {requested.y}");

        Debug.Log(
            $"{LOG} CurrentResolution = " +
            $"{current.x} x {current.y}");

        Debug.Log(
            $"{LOG} SensorResolution = " +
            $"{intrinsics.SensorResolution.x} x " +
            $"{intrinsics.SensorResolution.y}");

        if (texture != null)
        {
            Debug.Log(
                $"{LOG} TextureResolution = " +
                $"{texture.width} x {texture.height}");
        }
        else
        {
            Debug.LogWarning(
                $"{LOG} TextureResolution unavailable.");
        }

        // --------------------------------------------------------
        // Raw Meta sensor intrinsics
        // --------------------------------------------------------

        Debug.Log(
            $"{LOG} Sensor fx = " +
            $"{intrinsics.FocalLength.x:F6}");

        Debug.Log(
            $"{LOG} Sensor fy = " +
            $"{intrinsics.FocalLength.y:F6}");

        Debug.Log(
            $"{LOG} Sensor cx = " +
            $"{intrinsics.PrincipalPoint.x:F6}");

        Debug.Log(
            $"{LOG} Sensor cy = " +
            $"{intrinsics.PrincipalPoint.y:F6}");

        // --------------------------------------------------------
        // Validate resolution
        // --------------------------------------------------------

        if (intrinsics.SensorResolution.x <= 0 ||
            intrinsics.SensorResolution.y <= 0 ||
            current.x <= 0 ||
            current.y <= 0)
        {
            Debug.LogError(
                $"{LOG} ERROR: Invalid sensor/current resolution.");

            return;
        }

        // --------------------------------------------------------
        // Correct sensor coordinates for the actual image crop.
        //
        // Current Quest stream:
        //
        // SensorResolution  = 1280 x 1280
        // CurrentResolution = 1280 x 960
        //
        // The stream behaves as a centered vertical crop.
        //
        // Cropping does NOT scale fx/fy.
        // Cropping shifts cx/cy.
        // --------------------------------------------------------

        float cropX =
            (intrinsics.SensorResolution.x - current.x)
            / 2.0f;

        float cropY =
            (intrinsics.SensorResolution.y - current.y)
            / 2.0f;

        float imageFx =
            intrinsics.FocalLength.x;

        float imageFy =
            intrinsics.FocalLength.y;

        float imageCx =
            intrinsics.PrincipalPoint.x - cropX;

        float imageCy =
            intrinsics.PrincipalPoint.y - cropY;

        Debug.Log(
            $"{LOG} CropX = {cropX:F6}");

        Debug.Log(
            $"{LOG} CropY = {cropY:F6}");

        Debug.Log(
            $"{LOG} Image fx = {imageFx:F6}");

        Debug.Log(
            $"{LOG} Image fy = {imageFy:F6}");

        Debug.Log(
            $"{LOG} Image cx = {imageCx:F6}");

        Debug.Log(
            $"{LOG} Image cy = {imageCy:F6}");

        // --------------------------------------------------------
        // AprilTag configuration
        // --------------------------------------------------------

        Debug.Log(
            $"{LOG} TagFamily = {tagFamily}");

        Debug.Log(
            $"{LOG} TagId = {tagId}");

        Debug.Log(
            $"{LOG} TagSizeMeters = " +
            $"{tagSizeMeters:F6}");
    }

    // ============================================================
    // Capture one AprilTag camera frame
    // ============================================================

    private IEnumerator CaptureFrame()
    {
        isCapturing = true;

        Debug.Log(
            $"{LOG} Waiting for fresh camera frame...");

        // Wait until PCA reports a newly updated image.
        while (!cameraAccess.IsUpdatedThisFrame)
        {
            yield return null;
        }

        // --------------------------------------------------------
        // Capture timestamp and camera pose for the same
        // most-recent camera image.
        // --------------------------------------------------------

        DateTime timestamp =
            cameraAccess.Timestamp;

        Pose cameraPose =
            cameraAccess.GetCameraPose();

        var intrinsics =
            cameraAccess.Intrinsics;

        Vector2Int requested =
            cameraAccess.RequestedResolution;

        Vector2Int current =
            cameraAccess.CurrentResolution;

        Texture cameraTexture =
            cameraAccess.GetTexture();

        // --------------------------------------------------------
        // Validate resolutions
        // --------------------------------------------------------

        if (current.x <= 0 ||
            current.y <= 0)
        {
            Debug.LogError(
                $"{LOG} ERROR: Invalid CurrentResolution.");

            isCapturing = false;
            yield break;
        }

        if (intrinsics.SensorResolution.x <= 0 ||
            intrinsics.SensorResolution.y <= 0)
        {
            Debug.LogError(
                $"{LOG} ERROR: Invalid SensorResolution.");

            isCapturing = false;
            yield break;
        }

        // ========================================================
        // Correct camera intrinsics for saved PNG coordinates
        // ========================================================

        float cropX =
            (intrinsics.SensorResolution.x - current.x)
            / 2.0f;

        float cropY =
            (intrinsics.SensorResolution.y - current.y)
            / 2.0f;

        // Cropping preserves focal length.
        float imageFx =
            intrinsics.FocalLength.x;

        float imageFy =
            intrinsics.FocalLength.y;

        // Principal point shifts according to crop offset.
        float imageCx =
            intrinsics.PrincipalPoint.x - cropX;

        float imageCy =
            intrinsics.PrincipalPoint.y - cropY;

        // ========================================================
        // Obtain raw camera pixels
        // ========================================================

        var pixels =
            cameraAccess.GetColors();

        if (pixels == null ||
            pixels.Length == 0)
        {
            Debug.LogError(
                $"{LOG} ERROR: Camera returned no pixels.");

            isCapturing = false;
            yield break;
        }

        // --------------------------------------------------------
        // Create/re-create snapshot texture if necessary
        // --------------------------------------------------------

        if (snapshotTexture == null ||
            snapshotTexture.width != current.x ||
            snapshotTexture.height != current.y)
        {
            if (snapshotTexture != null)
            {
                Destroy(snapshotTexture);
            }

            snapshotTexture =
                new Texture2D(
                    current.x,
                    current.y,
                    TextureFormat.RGBA32,
                    false);
        }

        // --------------------------------------------------------
        // Copy raw PCA image into Texture2D
        // --------------------------------------------------------

        snapshotTexture.LoadRawTextureData(
            pixels);

        snapshotTexture.Apply(
            false,
            false);

        // ========================================================
        // Generate capture filename
        // ========================================================

        captureIndex++;

        string frameId =
            $"quest_tag_{captureIndex:D4}";

        string outputDirectory =
            Path.Combine(
                Application.persistentDataPath,
                "QuestAprilTagCaptures");

        Directory.CreateDirectory(
            outputDirectory);

        string imagePath =
            Path.Combine(
                outputDirectory,
                frameId + ".png");

        string jsonPath =
            Path.Combine(
                outputDirectory,
                frameId + ".json");

        // ========================================================
        // Save PNG
        // ========================================================

        byte[] pngBytes =
            snapshotTexture.EncodeToPNG();

        File.WriteAllBytes(
            imagePath,
            pngBytes);

        // ========================================================
        // Camera sensor pose relative to headset
        // ========================================================

        Pose lensOffset =
            intrinsics.LensOffset;

        // ========================================================
        // Build JSON metadata
        // ========================================================

        CaptureMetadata metadata =
            new CaptureMetadata
            {
                // ------------------------------------------------
                // Frame
                // ------------------------------------------------

                frame_id =
                    frameId,

                camera =
                    cameraAccess.CameraPosition.ToString(),

                timestamp =
                    timestamp.ToString("O"),

                // ------------------------------------------------
                // Requested resolution
                // ------------------------------------------------

                requested_width =
                    requested.x,

                requested_height =
                    requested.y,

                // ------------------------------------------------
                // Actual runtime stream resolution
                // ------------------------------------------------

                current_width =
                    current.x,

                current_height =
                    current.y,

                // ------------------------------------------------
                // Texture resolution
                // ------------------------------------------------

                texture_width =
                    cameraTexture != null
                        ? cameraTexture.width
                        : -1,

                texture_height =
                    cameraTexture != null
                        ? cameraTexture.height
                        : -1,

                // ------------------------------------------------
                // Static sensor calibration resolution
                // ------------------------------------------------

                sensor_width =
                    intrinsics.SensorResolution.x,

                sensor_height =
                    intrinsics.SensorResolution.y,

                // ------------------------------------------------
                // Crop offset
                // ------------------------------------------------

                crop_x =
                    cropX,

                crop_y =
                    cropY,

                // ------------------------------------------------
                // Raw sensor-space calibration
                // ------------------------------------------------

                sensor_fx =
                    intrinsics.FocalLength.x,

                sensor_fy =
                    intrinsics.FocalLength.y,

                sensor_cx =
                    intrinsics.PrincipalPoint.x,

                sensor_cy =
                    intrinsics.PrincipalPoint.y,

                // ------------------------------------------------
                // Calibration corresponding to saved PNG
                // ------------------------------------------------

                image_fx =
                    imageFx,

                image_fy =
                    imageFy,

                image_cx =
                    imageCx,

                image_cy =
                    imageCy,

                // ------------------------------------------------
                // Dynamic Quest camera world pose
                // ------------------------------------------------

                camera_world_position =
                    new Vector3Data(
                        cameraPose.position),

                camera_world_quaternion =
                    new QuaternionData(
                        cameraPose.rotation),

                // ------------------------------------------------
                // Static RGB camera pose relative to headset
                // ------------------------------------------------

                camera_relative_to_headset_position =
                    new Vector3Data(
                        lensOffset.position),

                camera_relative_to_headset_quaternion =
                    new QuaternionData(
                        lensOffset.rotation),

                // ------------------------------------------------
                // Frame documentation
                // ------------------------------------------------

                coordinate_system =
                    "Unity: +X right, +Y up, +Z forward",

                intrinsics_mapping =
                    "Saved image uses centered crop of sensor coordinates",

                // ------------------------------------------------
                // AprilTag configuration
                // ------------------------------------------------

                tag_family =
                    tagFamily,

                tag_id =
                    tagId,

                tag_size_m =
                    tagSizeMeters
            };

        // ========================================================
        // Save JSON
        // ========================================================

        string json =
            JsonUtility.ToJson(
                metadata,
                true);

        File.WriteAllText(
            jsonPath,
            json);

        // ========================================================
        // Diagnostic output
        // ========================================================

        Debug.Log(
            $"{LOG} SAVED {frameId}");

        Debug.Log(
            $"{LOG} PNG = {imagePath}");

        Debug.Log(
            $"{LOG} JSON = {jsonPath}");

        Debug.Log(
            $"{LOG} SavedImageResolution = " +
            $"{snapshotTexture.width} x " +
            $"{snapshotTexture.height}");

        Debug.Log(
            $"{LOG} CropX = {cropX:F6}");

        Debug.Log(
            $"{LOG} CropY = {cropY:F6}");

        Debug.Log(
            $"{LOG} SensorIntrinsics: " +
            $"fx={intrinsics.FocalLength.x:F6}, " +
            $"fy={intrinsics.FocalLength.y:F6}, " +
            $"cx={intrinsics.PrincipalPoint.x:F6}, " +
            $"cy={intrinsics.PrincipalPoint.y:F6}");

        Debug.Log(
            $"{LOG} ImageIntrinsics: " +
            $"fx={imageFx:F6}, " +
            $"fy={imageFy:F6}, " +
            $"cx={imageCx:F6}, " +
            $"cy={imageCy:F6}");

        Debug.Log(
            $"{LOG} Timestamp = {timestamp:O}");

        Debug.Log(
            $"{LOG} CameraWorldPosition = " +
            $"({cameraPose.position.x:F6}, " +
            $"{cameraPose.position.y:F6}, " +
            $"{cameraPose.position.z:F6})");

        Debug.Log(
            $"{LOG} CameraWorldQuaternion = " +
            $"({cameraPose.rotation.x:F6}, " +
            $"{cameraPose.rotation.y:F6}, " +
            $"{cameraPose.rotation.z:F6}, " +
            $"{cameraPose.rotation.w:F6})");

        Debug.Log(
            $"{LOG} Capture complete.");

        isCapturing = false;
    }

    // ============================================================
    // Cleanup
    // ============================================================

    private void OnDestroy()
    {
        if (snapshotTexture != null)
        {
            Destroy(snapshotTexture);
        }
    }
}