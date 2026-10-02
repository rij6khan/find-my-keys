# Meta Quest 3 Setup Instructions — Find My Keys

This guide explains how to set up a **Meta Quest 3 / Quest 3S**, prepare a Windows development computer, clone the **Find My Keys** GitHub repository, open the correct Unity project, and deploy the object-detection application to the headset.

The instructions are written for a new developer starting from a clean computer.

> **Repository:** `https://github.com/rij6khan/find-my-keys`  
> **Unity project to open:** `MetaQuest_ObjectDetection`  
> **Tested Unity version:** `6000.0.66f2`

---

## 1. Requirements

### Hardware

You need:

- Meta Quest 3 or Meta Quest 3S
- Windows development computer
- Meta Quest Touch controllers
- USB-C cable that supports **data transfer**
- Internet connection
- Android or iOS phone with the Meta Horizon app

> A charge-only USB-C cable is not sufficient for ADB or Unity deployment.

### Accounts

Prepare:

- Meta account
- Verified Meta developer account
- Membership in a Meta developer team
- Unity account
- GitHub account

### Software

Install or prepare:

- Meta Horizon mobile app
- Meta Quest Developer Hub (MQDH)
- Unity Hub
- Unity `6000.0.66f2`
- Android Build Support for Unity
- Android SDK & NDK Tools
- OpenJDK
- Git
- Git LFS
- Android Platform Tools / ADB

---

# Part I — Prepare the Meta Account and Quest

## 2. Complete the Normal Quest Setup

If the headset is new, complete the standard Quest setup before configuring it for development.

1. Turn on the Quest.
2. Connect it to Wi-Fi.
3. Sign in with the Meta account that will be used for development.
4. Install the **Meta Horizon** mobile app on the phone.
5. Sign in to the Meta Horizon app using the same Meta account.
6. Pair the headset with the Meta Horizon app.
7. Allow the headset to finish any required system updates.
8. Restart the headset after an update if requested.

For the Passthrough Camera API used by this project, use a current Horizon OS release. The upstream Meta sample requires Horizon OS v74 or newer.

---

## 3. Verify the Meta Developer Account

Developer Mode requires a Meta developer account associated with a developer team.

Before continuing:

1. Sign in to the Meta Developer Dashboard.
2. Verify the Meta account if verification has not already been completed.
3. Join an existing developer team or create one.
4. Confirm that the Meta account used in the Developer Dashboard is the same account being used in the Meta Horizon mobile app.

If Developer Mode does not appear in the mobile app, account verification or developer-team membership is one of the first things to check.

Official Meta developer setup:

`https://developers.meta.com/`

---

## 4. Enable Developer Mode

Developer Mode is enabled from the **Meta Horizon mobile app**, not directly from the headset.

On the phone:

1. Open **Meta Horizon**.
2. Tap the **headset/device icon**.
3. Select the paired Quest headset.
4. Open **Headset Settings**.
5. Select **Developer Mode**.
6. Turn **Developer Mode** ON.

The exact labels can change slightly between Meta Horizon app versions, but the path should be similar to:

```text
Meta Horizon
→ Headset / Devices
→ Select Quest
→ Headset Settings
→ Developer Mode
→ ON
```

After turning Developer Mode on:

1. Keep the headset powered on.
2. Restart the headset if Developer Mode does not appear to take effect.
3. Reopen the Meta Horizon app and confirm that Developer Mode remains ON.

### Checkpoint 1

Developer Mode must be enabled before continuing.

---

## 5. Enable the Quest Developer USB Option

Put on the Quest.

Open:

```text
Quick Control
→ Settings
→ Developer
```

Enable:

```text
MTP Notification
```

This makes USB connection prompts easier to access during development.

If the **Developer** section is missing:

- confirm Developer Mode is enabled in the Meta Horizon mobile app;
- verify the correct Meta account is being used;
- restart the headset.

---

## 6. Connect the Quest to the Computer

Use a USB-C cable that supports data.

1. Connect the Quest directly to the Windows computer.
2. Put on the headset.
3. Keep the headset awake.
4. Watch for a USB-debugging prompt.

You should see a prompt similar to:

```text
Allow USB debugging?
```

Select:

```text
Always allow from this computer
```

and then:

```text
Allow
```

If a USB file-access prompt also appears, it is safe to allow it for development.

> The USB-debugging authorization must be accepted **inside the headset**.

### If the debugging prompt does not appear

Try:

1. Disconnect the USB cable.
2. Restart the Quest.
3. Confirm Developer Mode is still ON.
4. Reconnect the cable.
5. Put on the headset immediately.
6. Check the notifications/USB prompt again.

---

# Part II — Configure Windows for Quest Development

## 7. Install the Meta/Oculus ADB Driver

Windows may require Meta's ADB driver before `adb` can communicate correctly with the headset.

Download the Oculus/Meta ADB driver from Meta's developer website.

After downloading it:

1. Extract the driver ZIP file.
2. Open the extracted folder.
3. Find the `.inf` driver file, typically:

```text
android_winusb.inf
```

4. Right-click the `.inf` file.
5. Select **Install**.
6. Accept the Windows security prompt if one appears.

After installation:

1. Disconnect the Quest.
2. Reconnect it.
3. Put on the headset.
4. Approve USB debugging again if requested.

---

## 8. Install Meta Quest Developer Hub

Install **Meta Quest Developer Hub (MQDH)**.

Sign in using the same Meta developer credentials associated with the headset.

MQDH is useful for:

- verifying device connectivity
- installing APK files
- viewing installed development apps
- capturing screenshots
- recording headset video
- casting the headset view
- collecting logs
- checking device information

### Verify the headset in MQDH

Open:

```text
Meta Quest Developer Hub
→ Device Manager
```

The connected headset should appear with an active/connected status.

If more than one headset is connected, select the correct headset from the device selector.

### Checkpoint 2

MQDH should recognize the Quest before continuing.

---

## 9. Install Android Platform Tools

Install Google's Android Platform Tools if `adb` is not already available.

A simple location is:

```text
C:\Android\platform-tools
```

Open Command Prompt:

```bat
cd /d "C:\Android\platform-tools"
```

Check ADB:

```bat
adb version
```

You should receive version information rather than:

```text
'adb' is not recognized...
```

---

## 10. Verify the Quest with ADB

With the Quest connected and awake, run:

```bat
adb devices
```

Expected format:

```text
List of devices attached
XXXXXXXXXXXX    device
```

The serial number is unique to each headset.

### Correct status

```text
device
```

means the Quest is authorized and ready.

### If the status is `unauthorized`

Example:

```text
XXXXXXXXXXXX    unauthorized
```

Do this:

1. Put on the headset.
2. Find the USB-debugging prompt.
3. Select **Always allow from this computer**.
4. Select **Allow**.
5. Run:

```bat
adb devices
```

again.

### If no device appears

Run:

```bat
adb kill-server
adb start-server
adb devices
```

If the Quest still does not appear, check:

- Developer Mode is ON
- headset is awake
- cable supports data
- USB port works
- Meta/Oculus ADB driver is installed
- USB-debugging request was accepted
- Windows can see the headset

### Check for multiple ADB installations

If the device repeatedly appears and disappears, Windows may be using more than one ADB installation.

Run:

```bat
where adb
```

If several copies are shown, use the ADB executable from the Android SDK/platform-tools installation associated with your development environment.

### Checkpoint 3

Do not continue until:

```bat
adb devices
```

shows the headset with:

```text
device
```

---

# Part III — Install the Development Software

## 11. Install Git

Install Git for Windows:

`https://git-scm.com/download/win`

Verify:

```bat
git --version
```

---

## 12. Install Git LFS

The repository contains neural-network model files managed with Git LFS.

Install Git LFS:

`https://git-lfs.com/`

Verify:

```bat
git lfs version
```

Initialize it:

```bat
git lfs install
```

Expected:

```text
Git LFS initialized.
```

> Install Git LFS **before cloning the project** so that the YOLO model assets are retrieved correctly.

---

## 13. Install Unity Hub

Install Unity Hub:

`https://unity.com/download`

Sign in with a Unity account.

---

## 14. Install the Correct Unity Version

This repository was saved using:

```text
Unity 6000.0.66f2
```

Install this version through Unity Hub.

If it is not shown in the normal Unity Hub list, use the Unity Download Archive:

`https://unity.com/releases/editor/archive`

### Required Unity modules

For Unity `6000.0.66f2`, install:

```text
Android Build Support
├── Android SDK & NDK Tools
└── OpenJDK
```

In Unity Hub:

```text
Installs
→ Unity 6000.0.66f2
→ Options / Add modules
```

Enable all three Android components.

> Do not intentionally upgrade the project to another Unity version during initial setup. First reproduce the project using `6000.0.66f2`.

### Checkpoint 4

Unity Hub should show:

```text
Unity 6000.0.66f2
Android Build Support installed
Android SDK & NDK Tools installed
OpenJDK installed
```

---

# Part IV — Download the Find My Keys Project

## 15. Clone the Repository

Choose a development directory.

Example:

```text
D:\Robotics design
```

Open Command Prompt:

```bat
cd /d "D:\Robotics design"
```

Clone:

```bat
git clone https://github.com/rij6khan/find-my-keys.git
```

Enter the repository:

```bat
cd /d "D:\Robotics design\find-my-keys"
```

Initialize Git LFS for this checkout:

```bat
git lfs install
```

Download all LFS-managed files:

```bat
git lfs pull
```

Verify:

```bat
git lfs ls-files
```

Expected model entries include paths ending in:

```text
yolov9onnx.onnx
yolov9sentis.sentis
```

---

## 16. Verify the YOLO Model Files Before Opening Unity

From the repository root, verify:

```bat
dir /s /b *.onnx
```

and:

```bat
dir /s /b *.sentis
```

Expected paths include:

```text
MetaQuest_ObjectDetection\Assets\PassthroughCameraApiSamples\MultiObjectDetection\SentisInference\Model\yolov9onnx.onnx
```

and:

```text
MetaQuest_ObjectDetection\Assets\PassthroughCameraApiSamples\MultiObjectDetection\SentisInference\Model\yolov9sentis.sentis
```

If either model is missing:

```bat
git lfs pull
```

### Checkpoint 5

Both model files must exist before opening the project in Unity.

---

# Part V — Open and Configure the Unity Project

## 17. Open the Correct Project Folder

Open Unity Hub.

Select:

```text
Projects
→ Add / Open
```

Choose:

```text
D:\Robotics design\find-my-keys\MetaQuest_ObjectDetection
```

### Important

Open:

```text
MetaQuest_ObjectDetection
```

Do **not** open:

```text
D:\Robotics design\find-my-keys
```

The GitHub repository root contains multiple project folders and is not itself the Unity project.

Use:

```text
Unity 6000.0.66f2
```

when Unity Hub asks which editor to use.

---

## 18. Wait for the First Import to Finish

The first launch can take several minutes.

Unity may need to:

- restore packages
- create the local `Library` directory
- import assets
- import the YOLO models
- compile C# scripts
- initialize XR packages

Do not close Unity while package restoration/import is still running.

---

## 19. Check the Unity Console

Open:

```text
Window
→ General
→ Console
```

The required state is:

```text
0 red compilation errors
```

Yellow warnings do not necessarily block deployment, but red errors must be resolved before building.

### Checkpoint 6

Do not proceed to Quest deployment until Unity compiles without red errors.

---

## 20. Verify the Installed Project Packages

The committed project uses:

```text
Meta MR Utility Kit          85.0.0
Unity Inference Engine       2.2.1
XR Plug-in Management        4.5.4
OpenXR Plugin                1.15.1
Android Logcat               1.4.7
```

Normally, let Unity restore these versions from:

```text
MetaQuest_ObjectDetection\Packages\manifest.json
```

Do not manually upgrade packages during initial reproduction.

---

# Part VI — Configure Unity for Quest

## 21. Switch the Build Platform to Android

In Unity:

```text
File
→ Build Profiles
→ Android
```

If Android is not active:

```text
Switch Platform
```

Wait for Unity to finish any platform-specific reimport.

Expected:

```text
Android
Active
```

If Android does not appear, close Unity and install the missing Android modules from Unity Hub.

---

## 22. Verify OpenXR

Open:

```text
Edit
→ Project Settings
→ XR Plug-in Management
```

Select the Android target.

Verify that:

```text
OpenXR
```

is enabled.

Then inspect the OpenXR feature settings.

The project should include the Meta Quest/OpenXR support required by the committed configuration, including the Quest controller interaction profile.

Depending on the package UI, you may see names such as:

```text
Meta XR Feature Group
Meta Quest Support
Oculus Touch Controller Profile
```

Do not enable unrelated XR providers during initial setup.

---

## 23. Run the Meta Project Setup Tool

Open Meta's Project Setup Tool from the Unity Meta/Meta XR tools menu.

Select the Android build target.

Review the project checks.

Fix all items marked as required/error.

The target condition is:

```text
0 required errors
```

Recommendations that are unrelated to physical-headset testing can be reviewed separately.

---

## 24. Verify Camera and Scene Permissions

The repository already includes the Android manifest needed by this project.

Path:

```text
MetaQuest_ObjectDetection
└── Assets
    └── Plugins
        └── Android
            └── AndroidManifest.xml
```

It includes the Quest headset-camera permission:

```xml
<uses-permission android:name="horizonos.permission.HEADSET_CAMERA" />
```

The project also includes scene/passthrough-related declarations.

Runtime permission handling is already present in:

```text
Assets
└── PassthroughCameraApiSamples
    └── PassthroughCamera
        └── Scripts
            └── RequestPermissionsOnce.cs
```

Do not add another permission script unless there is a specific runtime problem that requires it.

---

## 25. Verify the Build Scenes

Open:

```text
File
→ Build Profiles
```

The project should include these enabled scenes:

```text
0  StartScene
1  CameraViewer
2  CameraToWorld
3  BrightnessEstimation
4  MultiObjectDetection
5  ShaderSample
```

`StartScene` should be first.

---

## 26. Open MultiObjectDetection for Inspection

To inspect the main object-detection scene directly:

```text
Project
→ Assets
→ PassthroughCameraApiSamples
→ MultiObjectDetection
→ MultiObjectDetection.unity
```

Do not modify the scene just to perform the initial reproduction test.

---

# Part VII — Deploy to the Quest

## 27. Recheck the Quest Connection

Before building, open Command Prompt and run:

```bat
adb devices
```

Required:

```text
<Quest serial>    device
```

Also check MQDH:

```text
Device Manager
→ Quest
→ Active / Connected
```

Keep the Quest awake.

---

## 28. Select the Quest as Unity's Run Device

In Unity:

```text
File
→ Build Profiles
→ Android
```

Find **Run Device**.

Select the connected Quest.

It may appear by device name or serial number.

Expected configuration:

```text
Platform: Android
Status: Active
Run Device: connected Meta Quest
```

If the device does not appear:

1. run `adb devices`;
2. reconnect USB;
3. wake the headset;
4. reauthorize USB debugging if requested;
5. refresh Unity's device list.

---

## 29. Build and Run

In Unity:

```text
File
→ Build Profiles
→ Android
→ Build And Run
```

If Unity asks where to save the APK, choose a local build directory.

Example:

```text
Builds\FindMyKeys.apk
```

Unity should then:

```text
Compile
→ Build APK
→ Install APK through ADB
→ Launch the application on Quest
```

A successful build should finish without a red build error.

---

## 30. Approve Runtime Permissions in the Headset

The first time the application runs, the Quest may request permissions.

Put on the headset and approve the permissions required by the application, especially camera/scene-related permissions.

If a required permission is denied accidentally:

1. close the application;
2. open Quest Settings;
3. inspect the application's permissions;
4. allow the required permission;
5. relaunch the application.

If necessary, uninstall the development build and deploy it again to retest the first-run permission flow.

---

## 31. Find the App if Unity Does Not Launch It Automatically

Sideloaded development applications are available through **Unknown Sources**.

On the Quest:

```text
Library
→ Unknown Sources
```

Select the application.

The exact Library layout may change with Horizon OS updates, but development APKs should be available under **Unknown Sources** after installation.

You can also use MQDH to inspect installed development apps.

---

# Part VIII — Verify the Installation

## 32. Test CameraViewer First

From the sample start menu, open:

```text
CameraViewer
```

Verify:

- the application remains running;
- camera access works;
- the camera/passthrough content is visible as expected;
- there is no permission failure.

If CameraViewer does not work, fix the camera/device setup before testing object detection.

---

## 33. Test MultiObjectDetection

Return to the sample menu.

Open:

```text
MultiObjectDetection
```

Look at common objects supported by the supplied YOLO model, for example:

- bottle
- cup
- book
- cell phone
- laptop
- mouse
- remote
- TV/monitor

The working project should display:

```text
green detection boxes
object class labels
confidence percentage
```

The confidence value is already included in the pushed repository version.

---

## 34. Verify Controller Input

While `MultiObjectDetection` is running:

### A button

Press **A** to create markers for detected objects.

### B button

Press **B** to clear the spawned markers.

If the buttons do not work:

- confirm both controllers are connected;
- confirm the correct OpenXR controller profile is active;
- restart the application if controller tracking was unavailable during startup.

---

# Part IX — MQDH Tools for Testing

## 35. Cast the Headset

For demonstrations:

```text
MQDH
→ Device Manager
→ connected Quest
→ Cast
```

This lets another person see the Quest view on the computer.

---

## 36. Capture Screenshots

Use MQDH's screenshot function while the application is running.

This is preferable during development to opening another Quest camera application that could interrupt the Unity app.

---

## 37. Record Video

Use MQDH's recording controls to capture the Quest application during testing.

Save recordings outside the Unity project unless they are intentionally part of the repository.

---

# Part X — Troubleshooting

## 38. `adb` Is Not Recognized

If:

```text
'adb' is not recognized as an internal or external command
```

either navigate to Platform Tools:

```bat
cd /d "C:\Android\platform-tools"
```

and run:

```bat
adb devices
```

or add the Platform Tools directory to the Windows `PATH`.

---

## 39. Quest Shows `unauthorized`

Run:

```bat
adb devices
```

If you see:

```text
unauthorized
```

put on the headset and approve:

```text
Allow USB debugging
```

Select:

```text
Always allow from this computer
```

then run `adb devices` again.

---

## 40. Quest Does Not Appear in ADB

Check in this order:

```text
1. Developer Mode ON
2. Headset awake
3. Data-capable USB cable
4. Different USB port
5. Meta/Oculus ADB driver installed
6. USB-debugging prompt accepted
7. Restart ADB
8. Restart Quest
```

Restart ADB with:

```bat
adb kill-server
adb start-server
adb devices
```

---

## 41. Quest Appears and Disappears Repeatedly

Run:

```bat
where adb
```

If multiple ADB installations appear, different ADB daemons may be competing.

Use one consistent Android SDK/platform-tools installation.

---

## 42. Quest Is Visible in MQDH but Not Unity

First confirm:

```bat
adb devices
```

If ADB shows `device`:

1. keep the headset awake;
2. disconnect/reconnect USB;
3. reopen Build Profiles;
4. refresh the Run Device list;
5. restart Unity only if the device still does not appear.

---

## 43. Android Is Missing From Unity

In Unity Hub:

```text
Installs
→ 6000.0.66f2
→ Add modules
```

Install:

```text
Android Build Support
Android SDK & NDK Tools
OpenJDK
```

Then reopen the Unity project.

---

## 44. Unity Opens the Project With the Wrong Version

Close Unity.

In Unity Hub, explicitly open:

```text
find-my-keys\MetaQuest_ObjectDetection
```

with:

```text
6000.0.66f2
```

Do not accept an unintended project upgrade during initial setup.

---

## 45. YOLO Models Are Missing

From the repository root:

```bat
git lfs install
git lfs pull
git lfs ls-files
```

Verify:

```text
yolov9onnx.onnx
yolov9sentis.sentis
```

Then restart Unity if the models were downloaded after Unity had already opened.

---

## 46. Unity Has Red Compiler Errors

Do not build until the red errors are resolved.

First verify the working tree:

```bat
git status
```

If files were unintentionally modified, compare them with the GitHub version before manually editing code.

---

## 47. App Installs but Does Not Appear in the Normal Library

Open:

```text
Library
→ Unknown Sources
```

Development/sideloaded APKs are placed there.

---

## 48. App Opens but Camera Access Fails

Check:

- Quest 3 or Quest 3S is being used
- Developer Mode is ON
- Horizon OS is current
- required runtime permissions were allowed
- `horizonos.permission.HEADSET_CAMERA` is present
- CameraViewer works
- physical headset is being used
- no runtime errors appear in Android Logcat

---

## 49. MultiObjectDetection Opens but No Objects Are Detected

Check:

1. CameraViewer works first.
2. YOLO model files exist.
3. Git LFS downloaded the actual model files.
4. The room has reasonable lighting.
5. The object belongs to a class supported by the model.
6. Camera/scene permissions were approved.
7. No red runtime errors are shown.
8. The latest APK was actually installed.

---

# Part XI — Logs

## 50. Capture Android Logs

For a basic log capture:

```bat
adb logcat > quest_log.txt
```

Reproduce the problem.

Then stop capture with:

```text
Ctrl + C
```

For Unity-specific investigation, Unity's Android Logcat package can also be used.

---

# Part XII — Final Verification Checklist

A complete setup should pass every item below.

```text
[ ] Meta account configured
[ ] Meta developer account verified
[ ] Developer team membership confirmed
[ ] Quest paired with Meta Horizon app
[ ] Quest system software updated
[ ] Developer Mode enabled
[ ] Quest Developer settings visible
[ ] MTP Notification enabled
[ ] USB-C data connection established
[ ] USB debugging authorized
[ ] Meta/Oculus Windows ADB driver installed
[ ] MQDH installed
[ ] MQDH shows Quest active/connected
[ ] adb version works
[ ] adb devices shows "device"
[ ] Git installed
[ ] Git LFS installed
[ ] find-my-keys repository cloned
[ ] git lfs pull completed
[ ] yolov9onnx.onnx exists
[ ] yolov9sentis.sentis exists
[ ] Unity 6000.0.66f2 installed
[ ] Android Build Support installed
[ ] Android SDK & NDK Tools installed
[ ] OpenJDK installed
[ ] MetaQuest_ObjectDetection opened in Unity
[ ] Unity import completed
[ ] Unity Console has 0 red errors
[ ] Android is the active build platform
[ ] OpenXR is enabled
[ ] Meta Project Setup Tool has 0 required errors
[ ] Quest is selected as Run Device
[ ] Build And Run succeeds
[ ] Required runtime permissions approved
[ ] CameraViewer works
[ ] MultiObjectDetection works
[ ] Green detection boxes appear
[ ] Object class labels appear
[ ] Confidence percentage appears
[ ] A button places markers
[ ] B button clears markers
```

---

# Part XIII — Quick Setup Summary

For an already configured PC/headset:

```bat
git clone https://github.com/rij6khan/find-my-keys.git
cd find-my-keys
git lfs install
git lfs pull
git lfs ls-files
```

Open:

```text
find-my-keys\MetaQuest_ObjectDetection
```

with:

```text
Unity 6000.0.66f2
```

Verify the Quest:

```bat
adb devices
```

Then in Unity:

```text
File
→ Build Profiles
→ Android
→ select Quest as Run Device
→ Build And Run
```

On the headset, if the app does not launch automatically:

```text
Library
→ Unknown Sources
→ select the development app
```

---

# Official References

Meta developer portal:

`https://developers.meta.com/`

Meta device/developer setup:

`https://developers.meta.com/vr/documentation/android-apps/enable-developer-mode/`

Meta Quest Developer Hub:

`https://developers.meta.com/horizon/documentation/unreal/ts-mqdh-getting-started/`

Meta software setup:

`https://developers.meta.com/horizon/design/prototype-setup-software/`

Meta Passthrough Camera API sample:

`https://github.com/oculus-samples/Unity-PassthroughCameraApiSamples`

Android Platform Tools:

`https://developer.android.com/tools/releases/platform-tools`

Unity Download Archive:

`https://unity.com/releases/editor/archive`

Git:

`https://git-scm.com/`

Git LFS:

`https://git-lfs.com/`
