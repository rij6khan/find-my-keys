# Meta Quest 3 Camera Calibration and Pose Extraction Guide

## Purpose

This guide explains, step by step, how to extract the Quest 3 **left RGB passthrough camera** parameters needed for Quest ↔ YOR/robot synchronization and AprilTag-based calibration.

The procedure extracts:

| Quantity | Symbol / field | Static or dynamic? | Why it is needed |
|---|---|---|---|
| Focal length | `fx`, `fy` | Static | Camera projection / AprilTag pose estimation |
| Principal point | `cx`, `cy` | Static | Camera projection / AprilTag pose estimation |
| Sensor calibration resolution | `SensorResolution` | Static | Defines the coordinate system used by the reported sensor intrinsics |
| Actual camera stream resolution | `CurrentResolution` | Runtime | Confirms the resolution of the camera stream being used |
| Texture resolution | `GetTexture().width/height` | Runtime | Confirms the actual image dimensions passed to computer vision |
| Camera sensor pose relative to headset | `Intrinsics.LensOffset` | Static | Relates the RGB camera frame to the Quest headset frame |
| RGB camera world pose | `GetCameraPose()` | Dynamic | Gives the camera pose in Unity world coordinates for the current camera image |
| Camera image timestamp | `Timestamp` | Dynamic | Associates the image with its camera pose |

> **Important:** Meta's `PassthroughCameraAccess.Intrinsics` API exposes focal length, principal point, sensor resolution, and lens offset. It does **not** expose OpenCV-style distortion coefficients `k1, k2, p1, p2, k3`. Those must be obtained separately if Adam's AprilTag pipeline requires them.

---

# 1. Environment Used

The procedure below was implemented in the Meta Quest passthrough-camera project with:

- Meta Quest 3
- Unity 6.0
- Project editor version used: `6000.0.66f2`
- Meta XR / MRUK with `PassthroughCameraAccess`
- OpenXR
- Android build target
- Physical Quest headset connected through ADB
- Existing Meta `MultiObjectDetection` sample scene

Current scene:

```text
Assets/PassthroughCameraApiSamples/MultiObjectDetection/MultiObjectDetection.unity
```

Existing camera object:

```text
PassthroughCameraAccessPrefab
```

Current camera settings used in the Inspector:

```text
Camera Position:       Left
Requested Resolution: 1280 × 960
Max Framerate:         60
```

The existing camera component should be reused. **Do not create a second `PassthroughCameraAccess` component unless you intentionally want another camera stream.**

---

# 2. What the Meta API Provides

The relevant object is:

```csharp
Meta.XR.PassthroughCameraAccess
```

The important members are:

```csharp
cameraAccess.Intrinsics
cameraAccess.CurrentResolution
cameraAccess.GetCameraPose()
cameraAccess.Timestamp
cameraAccess.IsPlaying
cameraAccess.IsUpdatedThisFrame
cameraAccess.GetTexture()
```

The camera intrinsics structure contains:

```csharp
intrinsics.FocalLength
intrinsics.PrincipalPoint
intrinsics.SensorResolution
intrinsics.LensOffset
```

Interpretation:

```text
FocalLength.x      → fx
FocalLength.y      → fy

PrincipalPoint.x   → cx
PrincipalPoint.y   → cy

SensorResolution   → sensor calibration resolution

LensOffset.position
LensOffset.rotation
                   → pose of the RGB camera sensor relative to the headset
```

Meta describes `LensOffset` as the translation and orientation of the camera sensor **relative to the headset**.

For transform code, avoid an ambiguous label such as simply "camera-to-headset" unless the matrix convention is explicitly defined. A safer description is:

```text
Pose of the camera sensor expressed relative to the headset.
```

If using homogeneous matrices, document the convention used by Adam's script before multiplying transforms.

---

# 3. Camera Permission

The Quest application must have the headset camera permission:

```xml
<uses-permission android:name="horizonos.permission.HEADSET_CAMERA" />
```

The Meta sample project already requests passthrough camera access through its permission system.

In the sample project, the runtime permission is checked with:

```csharp
OVRPermissionsRequester.Permission.PassthroughCameraAccess
```

The camera data should not be read until permission is granted and the camera stream has started.

---

# 4. Create the Calibration Logger Script

Create this file:

```text
Assets/PassthroughCameraApiSamples/PassthroughCamera/Scripts/QuestCameraCalibrationLogger.cs
```

Open it in Visual Studio and replace the entire file with the code below.

```csharp
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

        // If the Inspector assignment is accidentally lost,
        // first try to find PassthroughCameraAccess on this object.
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

        Debug.Log(
            $"{LOG} RequestedResolution = " +
            $"{cameraAccess.RequestedResolution.x} x " +
            $"{cameraAccess.RequestedResolution.y}");

        // ---------------------------------------------------------
        // 1. Wait for runtime camera permission.
        // ---------------------------------------------------------

        bool permissionGranted =
            OVRPermissionsRequester.IsPermissionGranted(
                OVRPermissionsRequester.Permission.PassthroughCameraAccess);

        Debug.Log(
            $"{LOG} Initial camera permission = {permissionGranted}");

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
        // 2. Wait until the camera stream has produced an image.
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

        // ---------------------------------------------------------
        // 3. Wait for a fresh camera update.
        // ---------------------------------------------------------

        startTime = Time.realtimeSinceStartup;

        while (!cameraAccess.IsUpdatedThisFrame)
        {
            if (Time.realtimeSinceStartup - startTime >
                startupTimeoutSeconds)
            {
                Debug.LogWarning(
                    $"{LOG} WARNING: No IsUpdatedThisFrame event " +
                    "before timeout; reading the latest available frame.");
                break;
            }

            yield return null;
        }

        // ---------------------------------------------------------
        // 4. Print all calibration / pose information.
        // ---------------------------------------------------------

        PrintCalibration();

        Debug.Log($"{LOG} COMPLETE.");
    }

    private void PrintCalibration()
    {
        try
        {
            var intrinsics = cameraAccess.Intrinsics;

            Debug.Log(
                $"{LOG} Camera = {cameraAccess.CameraPosition}");

            // Requested stream resolution from the component.
            Debug.Log(
                $"{LOG} RequestedResolution = " +
                $"{cameraAccess.RequestedResolution.x} x " +
                $"{cameraAccess.RequestedResolution.y}");

            // Actual runtime camera stream resolution.
            Debug.Log(
                $"{LOG} CurrentResolution = " +
                $"{cameraAccess.CurrentResolution.x} x " +
                $"{cameraAccess.CurrentResolution.y}");

            // Sensor resolution associated with the static intrinsics.
            Debug.Log(
                $"{LOG} SensorResolution = " +
                $"{intrinsics.SensorResolution.x} x " +
                $"{intrinsics.SensorResolution.y}");

            // Actual texture dimensions.
            Texture cameraTexture = cameraAccess.GetTexture();

            if (cameraTexture != null)
            {
                Debug.Log(
                    $"{LOG} TextureResolution = " +
                    $"{cameraTexture.width} x {cameraTexture.height}");
            }
            else
            {
                Debug.LogWarning(
                    $"{LOG} TextureResolution unavailable: " +
                    "GetTexture() returned null.");
            }

            // Camera intrinsics.
            Debug.Log(
                $"{LOG} fx = {intrinsics.FocalLength.x:F6}");

            Debug.Log(
                $"{LOG} fy = {intrinsics.FocalLength.y:F6}");

            Debug.Log(
                $"{LOG} cx = {intrinsics.PrincipalPoint.x:F6}");

            Debug.Log(
                $"{LOG} cy = {intrinsics.PrincipalPoint.y:F6}");

            // Intrinsic matrix.
            Debug.Log(
                $"{LOG} K = [[" +
                $"{intrinsics.FocalLength.x:F6}, 0, " +
                $"{intrinsics.PrincipalPoint.x:F6}], " +
                $"[0, {intrinsics.FocalLength.y:F6}, " +
                $"{intrinsics.PrincipalPoint.y:F6}], " +
                $"[0, 0, 1]]");

            // Static camera sensor pose relative to the headset.
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

            // Dynamic camera world pose corresponding to the latest image.
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

            // Timestamp associated with the latest camera image.
            Debug.Log(
                $"{LOG} Timestamp = {cameraAccess.Timestamp:O}");
        }
        catch (System.Exception e)
        {
            Debug.LogError(
                $"{LOG} ERROR reading calibration: {e}");
        }
    }
}
```

Save the file:

```text
Ctrl + S
```

Return to Unity and wait for script compilation to finish.

---

# 5. Attach the Logger to the Existing Camera Object

Open:

```text
Assets
└── PassthroughCameraApiSamples
    └── MultiObjectDetection
        └── MultiObjectDetection.unity
```

In the **Hierarchy**, select:

```text
PassthroughCameraAccessPrefab
```

The object should already contain:

```text
Passthrough Camera Access (Script)
```

with approximately:

```text
Camera Position:       Left
Requested Resolution: 1280 × 960
Max Framerate:         60
```

Now add:

```text
Quest Camera Calibration Logger (Script)
```

There are two ways:

### Method A — Add Component

With `PassthroughCameraAccessPrefab` selected:

```text
Inspector
→ Add Component
→ search "Quest Camera Calibration Logger"
→ select it
```

### Method B — Drag the script

Drag:

```text
QuestCameraCalibrationLogger.cs
```

from the Project window onto:

```text
PassthroughCameraAccessPrefab
```

in the Hierarchy or Inspector.

---

# 6. Assign the Camera Reference

In the new component, locate:

```text
Camera Access
```

Drag the same:

```text
PassthroughCameraAccessPrefab
```

from the Hierarchy into this field.

Unity should show something equivalent to:

```text
Quest Camera Calibration Logger (Script)

Camera Access:
PassthroughCameraAccessPrefab (Passthrough Camera Access)

Startup Timeout Seconds:
20
```

This confirms that the logger is reading the same camera component already used by the object-detection pipeline.

---

# 7. Save the Scene

Press:

```text
Ctrl + S
```

Check the scene tab.

If the scene name appears as:

```text
MultiObjectDetection*
```

the `*` means there are unsaved scene changes.

After saving, it should appear as:

```text
MultiObjectDetection
```

with no `*`.

---

# 8. Check for Compilation Errors

Open:

```text
Window
→ General
→ Console
```

or use the Console tab already visible in Unity.

Before building:

```text
Red errors = 0
```

A yellow warning from an existing sample is not necessarily a blocker, but **do not build while the new calibration script has red compilation errors**.

---

# 9. Connect the Quest Through ADB

The Windows Platform Tools folder used here is:

```text
C:\Users\Adhwa\Downloads\platform-tools-latest-windows\platform-tools
```

Open Command Prompt and run:

```bat
cd /d "C:\Users\Adhwa\Downloads\platform-tools-latest-windows\platform-tools"
```

Then:

```bat
adb devices
```

Expected result:

```text
List of devices attached
2G97C5ZJ3503Z1    device
```

If the device says:

```text
unauthorized
```

put on the Quest and approve the USB debugging prompt.

If Windows says:

```text
'adb' is not recognized as an internal or external command
```

you are not currently inside the Platform Tools directory and ADB is not in the Windows PATH. Use the `cd /d` command above first.

---

# 10. Build and Deploy a Fresh APK

This step is essential.

If the logger was added after the previous APK was installed, launching the old APK will not run the new script.

In Unity:

```text
File
→ Build Profiles
→ Android
```

Verify:

```text
Android = Active
Run Device = Quest
```

Then choose:

```text
Build And Run
```

Wait until Unity reports messages similar to:

```text
Application installed to device
Launching application
Build completed with a result of 'Succeeded'
```

Make sure these timestamps are **after** the time when the calibration script was edited and compiled.

---

# 11. Clear Old ADB Logs Before the Calibration Run

Once the fresh app is installed and the Quest is connected, return to Command Prompt:

```bat
cd /d "C:\Users\Adhwa\Downloads\platform-tools-latest-windows\platform-tools"
```

Clear old Logcat data:

```bat
adb logcat -c
```

Do this **before entering the `MultiObjectDetection` scene**, otherwise the startup messages from the logger may be erased.

---

# 12. Start the Camera Scene on the Quest

Put on the Quest.

From the sample start menu, open:

```text
MultiObjectDetection
```

Wait until:

- passthrough video is visible;
- the camera is operating;
- YOLO/object-detection boxes appear.

Leave the application running for several seconds.

The logger runs automatically when the scene loads.

---

# 13. Extract the Calibration Output with ADB

Use one unique prefix:

```text
QUEST_CALIB:
```

This is intentionally used on every logger line.

Run:

```bat
adb logcat -d | findstr /I "QUEST_CALIB"
```

Do **not** search independently for strings such as:

```text
cy =
```

because unrelated Android messages such as:

```text
Low latency =
allowedCapturePolicy =
```

can contain the same character sequence and create false matches.

The unique `QUEST_CALIB` prefix prevents this problem.

---

# 14. Alternative: Read the Values in Unity Android Logcat

Instead of Command Prompt:

```text
Unity
→ Window
→ Analysis
→ Android Logcat
```

Select the running Quest application.

In the search box enter:

```text
QUEST_CALIB
```

Only the calibration messages should remain visible.

---

# 15. Expected Successful Output

A correct run should contain lines similar to:

```text
QUEST_CALIB: Awake. Object=PassthroughCameraAccessPrefab...
QUEST_CALIB: OnEnable.
QUEST_CALIB: Start entered.

QUEST_CALIB: Camera reference OK. CameraPosition=Left
QUEST_CALIB: RequestedResolution = 1280 x 960

QUEST_CALIB: Initial camera permission = True
QUEST_CALIB: Camera permission granted.

QUEST_CALIB: Waiting for camera IsPlaying...
QUEST_CALIB: Camera IsPlaying = TRUE.

QUEST_CALIB: Camera = Left

QUEST_CALIB: RequestedResolution = ...
QUEST_CALIB: CurrentResolution = ...
QUEST_CALIB: SensorResolution = ...
QUEST_CALIB: TextureResolution = ...

QUEST_CALIB: fx = ...
QUEST_CALIB: fy = ...
QUEST_CALIB: cx = ...
QUEST_CALIB: cy = ...

QUEST_CALIB: K = [[...], [...], [0, 0, 1]]

QUEST_CALIB: CameraRelativeToHeadset.Position = (...)
QUEST_CALIB: CameraRelativeToHeadset.Quaternion = (...)

QUEST_CALIB: WorldPosition = (...)
QUEST_CALIB: WorldQuaternion = (...)

QUEST_CALIB: Timestamp = ...

QUEST_CALIB: COMPLETE.
```

---

# 16. Meaning of Each Extracted Field

## 16.1 `fx`

Example:

```text
fx = 868.644700
```

This is the horizontal focal length reported by the Quest camera intrinsics.

It is used in the intrinsic matrix:

```text
K =
[ fx   0   cx ]
[  0  fy   cy ]
[  0   0    1 ]
```

---

## 16.2 `fy`

Example:

```text
fy = 868.644700
```

This is the vertical focal length.

---

## 16.3 `cx`

Example:

```text
cx = 643.879500
```

This is the x-coordinate of the principal point in the camera intrinsic coordinate system.

---

## 16.4 `cy`

Example:

```text
cy = 640.571500
```

This is the y-coordinate of the principal point.

---

# 17. Construct the Camera Matrix

Using the extracted values:

```text
fx = 868.644700
fy = 868.644700
cx = 643.879500
cy = 640.571500
```

the intrinsic matrix is:

```text
K =
[ 868.644700      0         643.879500 ]
[     0        868.644700   640.571500 ]
[     0            0             1      ]
```

In OpenCV/Python this is commonly represented as:

```python
import numpy as np

K = np.array([
    [868.644700,   0.0,        643.879500],
    [0.0,          868.644700, 640.571500],
    [0.0,          0.0,          1.0]
], dtype=np.float64)
```

---

# 18. Resolution: Important Distinction

The original Quest extraction returned:

```text
SensorResolution = 1280 x 1280
```

while the Unity Inspector requested:

```text
RequestedResolution = 1280 x 960
```

These are **not automatically the same concept**.

The updated logger therefore records all three:

```text
RequestedResolution
CurrentResolution
SensorResolution
TextureResolution
```

Definitions:

### `RequestedResolution`

What was requested in the Unity component.

Example:

```text
1280 × 960
```

### `CurrentResolution`

The runtime camera resolution selected by `PassthroughCameraAccess`.

Meta explicitly notes that `CurrentResolution` can differ from `RequestedResolution`.

### `SensorResolution`

The resolution stored with the **static sensor intrinsics**.

In the extraction already performed:

```text
1280 × 1280
```

### `TextureResolution`

The actual width and height of the camera texture returned by:

```csharp
cameraAccess.GetTexture()
```

For AprilTag/OpenCV processing, always record the actual image dimensions used by the detector.

> Do not blindly label `SensorResolution = 1280 × 1280` as the processed image resolution if the actual camera texture is different.

The original run did not log `CurrentResolution` or `TextureResolution`, which is why the updated logger adds them.

---

# 19. Static Camera Pose Relative to the Headset

The Quest returned:

```text
CameraRelativeToHeadset.Position =
(-0.032143, -0.017374, 0.062607)
```

Units:

```text
meters
```

and:

```text
CameraRelativeToHeadset.Quaternion =
(0.096907, 0.002825, 0.002974, 0.995285)
```

Quaternion order in the Unity `Quaternion` fields is:

```text
x, y, z, w
```

Meta describes `LensOffset` as the translation and orientation of the camera sensor relative to the headset.

For robotics code, document it as:

```text
Camera sensor pose relative to headset
```

rather than relying only on an arrow label whose matrix direction could be interpreted differently.

---

# 20. Dynamic RGB Camera World Pose

One captured run returned:

```text
WorldPosition =
(-0.060554, 1.097530, -0.004246)
```

and:

```text
WorldQuaternion =
(0.188253, -0.096148, 0.032422, 0.976865)
```

This pose is **dynamic**.

If the user moves their head, the values change.

Therefore:

```text
Do not treat WorldPosition or WorldQuaternion as fixed calibration constants.
```

They should be captured together with the corresponding camera image whenever they are needed for synchronization.

---

# 21. Timestamp

The extracted timestamp was:

```text
2026-10-14T04:02:27.4385640Z
```

`PassthroughCameraAccess.Timestamp` is associated with the latest camera image.

This is useful for associating:

```text
camera image
+
camera world pose
+
robot/YOR observation
```

during synchronization.

For an AprilTag capture, save the timestamp together with the image and pose.

---

# 22. Values Extracted from the Quest 3

The current verified extraction produced:

```text
Camera:
Left

Sensor calibration resolution:
1280 × 1280

fx:
868.644700

fy:
868.644700

cx:
643.879500

cy:
640.571500
```

Intrinsic matrix:

```text
K =
[ 868.644700      0         643.879500 ]
[     0        868.644700   640.571500 ]
[     0            0             1      ]
```

Camera sensor pose relative to headset:

```text
Position [m]:
(-0.032143, -0.017374, 0.062607)

Quaternion [x, y, z, w]:
(0.096907, 0.002825, 0.002974, 0.995285)
```

Example dynamic world pose:

```text
World position [m]:
(-0.060554, 1.097530, -0.004246)

World quaternion [x, y, z, w]:
(0.188253, -0.096148, 0.032422, 0.976865)
```

Timestamp:

```text
2026-10-14T04:02:27.4385640Z
```

The world pose above is an example from one camera frame and will change when the headset moves.

---

# 23. What Adam/YOR Needs from the Quest

For the Quest side of AprilTag-based synchronization, the useful data are:

```text
Static camera information
-------------------------
Camera side: Left
fx
fy
cx
cy
SensorResolution
Camera sensor pose relative to headset

Runtime image information
-------------------------
Actual camera image / AprilTag image
CurrentResolution
TextureResolution
Timestamp
WorldPosition
WorldQuaternion
```

If Adam's algorithm uses a standard OpenCV distortion vector, he also requested:

```text
k1
k2
p1
p2
k3
```

Those are not returned by the `PassthroughCameraAccess.Intrinsics` structure used in this guide.

---

# 24. How These Values Fit into Quest ↔ YOR Synchronization

A typical AprilTag synchronization workflow is conceptually:

```text
Quest camera image containing AprilTag
        +
Quest camera intrinsic matrix K
        +
Quest distortion model, if required
        ↓
Estimate AprilTag pose in Quest camera frame


YOR camera image containing the same AprilTag
        +
YOR camera intrinsic calibration
        +
YOR distortion model
        ↓
Estimate AprilTag pose in YOR camera frame


Common AprilTag observation
        ↓
Compute Quest-camera ↔ YOR-camera transform
```

If the final robot transform must be expressed relative to the **Quest headset** rather than the RGB camera sensor, then the static `LensOffset` pose is also needed:

```text
Quest RGB camera frame
        ↔
Quest headset frame
```

The exact matrix multiplication order depends on the transform convention in Adam's code.

---

# 25. For an Actual AprilTag Capture

For a reliable synchronization dataset, do not save only the static intrinsics once.

For every image used by Adam's calibration code, save together:

```text
1. RGB image
2. Camera side: Left
3. CurrentResolution
4. TextureResolution
5. Timestamp
6. WorldPosition
7. WorldQuaternion
```

The static values can be stored once:

```text
fx
fy
cx
cy
SensorResolution
LensOffset.position
LensOffset.rotation
```

This prevents a dynamic Quest pose from being accidentally paired with a different camera image.

---

# 26. Why `IsPlaying` Is Checked

The logger waits for:

```csharp
cameraAccess.IsPlaying
```

because this indicates that the component is enabled and has received a camera image.

Reading the camera pose/timestamp before the stream is ready can produce invalid or meaningless data.

The logger also waits for:

```csharp
cameraAccess.IsUpdatedThisFrame
```

so that the dynamic pose and timestamp are read after a fresh camera image update whenever possible.

---

# 27. Troubleshooting

## Problem A — No `QUEST_CALIB` Output

Run:

```bat
adb logcat -d | findstr /I "QUEST_CALIB"
```

If nothing appears, check:

```text
1. Is QuestCameraCalibrationLogger attached?
2. Is the component enabled?
3. Is Camera Access assigned?
4. Was the scene saved?
5. Was a fresh APK built after adding the script?
6. Did you actually enter MultiObjectDetection?
```

A common cause is that the APK installed on the Quest was built **before** the logger was added.

Rebuild:

```text
File
→ Build Profiles
→ Android
→ Build And Run
```

---

## Problem B — ADB Is Not Recognized

Error:

```text
'adb' is not recognized as an internal or external command
```

Fix:

```bat
cd /d "C:\Users\Adhwa\Downloads\platform-tools-latest-windows\platform-tools"
```

Then:

```bat
adb devices
```

---

## Problem C — False Log Matches

A command such as:

```bat
findstr /C:"cy ="
```

can match unrelated messages containing text such as:

```text
latency =
```

Use only:

```bat
adb logcat -d | findstr /I "QUEST_CALIB"
```

---

## Problem D — Camera Reference Is Null

If the output says:

```text
QUEST_CALIB: ERROR: PassthroughCameraAccess is NULL.
```

select:

```text
PassthroughCameraAccessPrefab
```

and verify:

```text
Quest Camera Calibration Logger
→ Camera Access
```

points to:

```text
PassthroughCameraAccessPrefab (Passthrough Camera Access)
```

---

## Problem E — Camera Permission Timeout

If:

```text
QUEST_CALIB: ERROR: Timed out waiting for Passthrough Camera permission.
```

verify:

- headset camera permission is declared;
- permission was accepted on the Quest;
- passthrough camera access is enabled in the project;
- the application is running on a supported physical headset.

---

## Problem F — `IsPlaying` Timeout

If:

```text
QUEST_CALIB: ERROR: Timed out waiting for PassthroughCameraAccess.IsPlaying.
```

verify that the camera feed itself works.

A strong practical test is:

```text
Does MultiObjectDetection show the passthrough image and YOLO boxes?
```

If yes, the stream is operating and the logger/component setup should be checked.

---

## Problem G — Scene Has an Asterisk

If Unity shows:

```text
MultiObjectDetection*
```

the scene contains unsaved changes.

Press:

```text
Ctrl + S
```

before building.

---

## Problem H — Multiple ADB Servers

Unity, Meta Quest Developer Hub, and a separately downloaded Android Platform Tools installation can each use ADB.

If Unity Android Logcat repeatedly disconnects or reports multiple ADB server instances, avoid launching several ADB versions unnecessarily.

For command-line extraction, consistently use:

```text
C:\Users\Adhwa\Downloads\platform-tools-latest-windows\platform-tools
```

and verify the device with:

```bat
adb devices
```

before reading Logcat.

---

# 28. Distortion Coefficients Are Still Missing

The following coefficients were requested for the YOR/AprilTag pipeline:

```text
k1
k2
p1
p2
k3
```

They are **not fields of**:

```csharp
PassthroughCameraAccess.Intrinsics
```

The Meta MRUK intrinsics structure documented for this API contains:

```text
FocalLength
PrincipalPoint
SensorResolution
LensOffset
```

Therefore the Unity logger above cannot truthfully invent or derive:

```text
k1, k2, p1, p2, k3
```

A separate method is required, such as obtaining supported native camera calibration metadata or performing an independent camera calibration procedure.

Do not use zero distortion coefficients unless the calibration/AprilTag pipeline has explicitly established that assumption.

---

# 29. Recommended Output File for Adam

After running the logger, save the Quest values in a simple text or JSON record such as:

```text
camera = Left

sensor_resolution = 1280 x 1280
current_resolution = <value from rerun>
texture_resolution = <value from rerun>

fx = 868.644700
fy = 868.644700
cx = 643.879500
cy = 640.571500

camera_relative_to_headset_position_m =
(-0.032143, -0.017374, 0.062607)

camera_relative_to_headset_quaternion_xyzw =
(0.096907, 0.002825, 0.002974, 0.995285)

world_position_m =
(-0.060554, 1.097530, -0.004246)

world_quaternion_xyzw =
(0.188253, -0.096148, 0.032422, 0.976865)

timestamp =
2026-10-14T04:02:27.4385640Z

distortion =
k1 = MISSING
k2 = MISSING
p1 = MISSING
p2 = MISSING
k3 = MISSING
```

For dynamic AprilTag captures, replace the world pose and timestamp with the values captured for that specific image.

---

# 30. Final Verification Checklist

Before giving the calibration to the YOR side, verify:

- [ ] Quest camera is `Left`.
- [ ] The camera stream is running.
- [ ] `fx` and `fy` are recorded.
- [ ] `cx` and `cy` are recorded.
- [ ] `SensorResolution` is recorded.
- [ ] `CurrentResolution` is recorded.
- [ ] `TextureResolution` is recorded.
- [ ] `LensOffset.position` is recorded.
- [ ] `LensOffset.rotation` is recorded.
- [ ] World camera position is recorded for each relevant capture.
- [ ] World camera quaternion is recorded for each relevant capture.
- [ ] Timestamp is recorded for each relevant capture.
- [ ] AprilTag image is paired with the correct pose/timestamp.
- [ ] Distortion coefficients are either extracted separately or explicitly handled by the calibration pipeline.
- [ ] Transform direction/convention is documented before combining Quest and YOR matrices.

---

# 31. Official References

Meta Horizon OS Developers — Getting Started with Passthrough Camera API in Unity:

https://developers.meta.com/vr/documentation/unity/unity-pca-documentation/

Meta Horizon OS Developers — `PassthroughCameraAccess` API reference:

https://developers.meta.com/vr/reference/mruk/v83/class_meta_x_r_passthrough_camera_access/

Meta Horizon OS Developers — CameraViewer sample:

https://developers.meta.com/vr/documentation/unity/unity-sample-camera-viewer/

Official Meta sample repository:

https://github.com/oculus-samples/Unity-PassthroughCameraApiSamples

The Meta API documentation describes:

- `Intrinsics` as static sensor intrinsics;
- `CurrentResolution` as the current runtime camera resolution, which can differ from the requested resolution;
- `LensOffset` as camera-sensor translation/orientation relative to the headset;
- `GetCameraPose()` as the passthrough camera world pose;
- `Timestamp` as the timestamp associated with the latest camera image.

---

## Summary

The Quest-side extraction path is:

```text
Quest 3
  ↓
PassthroughCameraAccess
  ↓
Intrinsics
  ├── fx
  ├── fy
  ├── cx
  ├── cy
  ├── SensorResolution
  └── LensOffset
  ↓
CurrentResolution / GetTexture()
  ↓
GetCameraPose()
  ↓
Timestamp
  ↓
QUEST_CALIB Logcat output
  ↓
Quest ↔ YOR / AprilTag calibration pipeline
```

The procedure successfully extracts the Quest camera intrinsics, static camera/headset relationship, dynamic camera world pose, and image timestamp. OpenCV-style distortion coefficients remain a separate calibration/metadata task.
