using System.Collections;
using Meta.XR;
using UnityEngine;

public class QuestCameraCalibrationLogger : MonoBehaviour
{
    private const string LOG = "QUEST_CALIB:";

    [SerializeField]
    private PassthroughCameraAccess cameraAccess;

    [SerializeField]
    private float startupTimeoutSeconds = 20f;

    private void Awake()
    {
        Debug.Log(
            $"{LOG} Awake. " +
            $"Object={gameObject.name}, " +
            $"Scene={gameObject.scene.name}, " +
            $"Active={gameObject.activeInHierarchy}, " +
            $"Enabled={enabled}");
    }

    private void OnEnable()
    {
        Debug.Log($"{LOG} OnEnable.");
    }

    private IEnumerator Start()
    {
        Debug.Log($"{LOG} Start entered.");

        // If the Inspector reference was lost, try the component
        // on this same GameObject automatically.
        if (cameraAccess == null)
        {
            cameraAccess = GetComponent<PassthroughCameraAccess>();

            if (cameraAccess != null)
            {
                Debug.Log(
                    $"{LOG} Camera reference automatically found " +
                    "on this GameObject.");
            }
        }

        if (cameraAccess == null)
        {
            Debug.LogError(
                $"{LOG} ERROR: PassthroughCameraAccess is NULL.");
            yield break;
        }

        Debug.Log(
            $"{LOG} Camera reference OK. " +
            $"CameraPosition={cameraAccess.CameraPosition}");

        bool permissionGranted =
            OVRPermissionsRequester.IsPermissionGranted(
                OVRPermissionsRequester.Permission.PassthroughCameraAccess);

        Debug.Log(
            $"{LOG} Initial camera permission = {permissionGranted}");

        // ---------------------------------------------------------
        // 1. Wait for camera permission.
        // ---------------------------------------------------------
        float startTime = Time.realtimeSinceStartup;

        while (!OVRPermissionsRequester.IsPermissionGranted(
                   OVRPermissionsRequester.Permission.PassthroughCameraAccess))
        {
            if (Time.realtimeSinceStartup - startTime >
                startupTimeoutSeconds)
            {
                Debug.LogError(
                    $"{LOG} ERROR: Timed out waiting for " +
                    "Passthrough Camera permission.");
                yield break;
            }

            yield return null;
        }

        Debug.Log($"{LOG} Camera permission granted.");

        // ---------------------------------------------------------
        // 2. Read static camera calibration.
        // ---------------------------------------------------------
        PrintIntrinsics();

        // ---------------------------------------------------------
        // 3. Wait for the physical camera stream.
        // ---------------------------------------------------------
        Debug.Log($"{LOG} Waiting for camera IsPlaying...");

        startTime = Time.realtimeSinceStartup;

        while (!cameraAccess.IsPlaying)
        {
            if (Time.realtimeSinceStartup - startTime >
                startupTimeoutSeconds)
            {
                Debug.LogError(
                    $"{LOG} ERROR: Timed out waiting for " +
                    "PassthroughCameraAccess.IsPlaying.");

                yield break;
            }

            yield return null;
        }

        Debug.Log($"{LOG} Camera IsPlaying = TRUE.");

        // Give the stream a couple of frames so the timestamp and
        // camera pose correspond to a valid recent camera image.
        yield return null;
        yield return null;

        // ---------------------------------------------------------
        // 4. Read dynamic pose + timestamp.
        // ---------------------------------------------------------
        PrintPoseAndTimestamp();

        Debug.Log($"{LOG} COMPLETE.");
    }

    private void PrintIntrinsics()
    {
        try
        {
            var intrinsics = cameraAccess.Intrinsics;

            Debug.Log(
                $"{LOG} Camera = {cameraAccess.CameraPosition}");

            Debug.Log(
                $"{LOG} SensorResolution = " +
                $"{intrinsics.SensorResolution.x} x " +
                $"{intrinsics.SensorResolution.y}");

            Debug.Log(
                $"{LOG} fx = {intrinsics.FocalLength.x:F6}");

            Debug.Log(
                $"{LOG} fy = {intrinsics.FocalLength.y:F6}");

            Debug.Log(
                $"{LOG} cx = {intrinsics.PrincipalPoint.x:F6}");

            Debug.Log(
                $"{LOG} cy = {intrinsics.PrincipalPoint.y:F6}");

            Pose lensOffset = intrinsics.LensOffset;

            Debug.Log(
                $"{LOG} CameraRelativeToHeadset.Position = " +
                $"({lensOffset.position.x:F6}, " +
                $"{lensOffset.position.y:F6}, " +
                $"{lensOffset.position.z:F6})");

            Debug.Log(
                $"{LOG} CameraRelativeToHeadset.Quaternion = " +
                $"({lensOffset.rotation.x:F6}, " +
                $"{lensOffset.rotation.y:F6}, " +
                $"{lensOffset.rotation.z:F6}, " +
                $"{lensOffset.rotation.w:F6})");

            Debug.Log(
                $"{LOG} K = [[" +
                $"{intrinsics.FocalLength.x:F6}, 0, " +
                $"{intrinsics.PrincipalPoint.x:F6}], " +
                $"[0, {intrinsics.FocalLength.y:F6}, " +
                $"{intrinsics.PrincipalPoint.y:F6}], " +
                $"[0, 0, 1]]");
        }
        catch (System.Exception e)
        {
            Debug.LogError(
                $"{LOG} ERROR reading intrinsics: {e}");
        }
    }

    private void PrintPoseAndTimestamp()
    {
        try
        {
            Pose cameraPose = cameraAccess.GetCameraPose();

            Debug.Log(
                $"{LOG} WorldPosition = " +
                $"({cameraPose.position.x:F6}, " +
                $"{cameraPose.position.y:F6}, " +
                $"{cameraPose.position.z:F6})");

            Debug.Log(
                $"{LOG} WorldQuaternion = " +
                $"({cameraPose.rotation.x:F6}, " +
                $"{cameraPose.rotation.y:F6}, " +
                $"{cameraPose.rotation.z:F6}, " +
                $"{cameraPose.rotation.w:F6})");

            Debug.Log(
                $"{LOG} Timestamp = {cameraAccess.Timestamp:O}");
        }
        catch (System.Exception e)
        {
            Debug.LogError(
                $"{LOG} ERROR reading pose/timestamp: {e}");
        }
    }
}