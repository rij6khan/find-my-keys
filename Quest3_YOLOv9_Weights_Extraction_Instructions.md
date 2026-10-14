# Meta Quest 3 YOLOv9: How to Locate, Inspect, and Export Model Weights

**Project:** Unity MetaQuest_ObjectDetection  
**Date verified:** October 14, 2026  
**Environment:** Windows Command Prompt (CMD), Python 3.10, ONNX

## 1. Verified result

The YOLOv9 ONNX file was found in the Unity source project. The APK was also located, but its earlier archive searches did **not** reveal a standalone `.onnx`, `.tflite`, `.sentis`, or `.nnmodel` file. Therefore, the commands below obtain weights from the **Unity project**, not demonstrably from the packaged APK.

| Item | Observed value |
|---|---|
| Model filename | `yolov9onnx.onnx` |
| ONNX file size | 7.95 MiB |
| Stored scalar values in ONNX initializers | 2,001,840 |
| Initializer tensors | 371 |
| ONNX graph nodes | 771 |

**Interpretation:** ONNX initializers store model parameters and potentially nontrainable constants. The 771 graph nodes are ONNX operations, **not** necessarily 771 neural-network layers.

## 2. Locate the original ONNX model

Open **CMD** and run:

```cmd
dir /s /b "D:\Robotics design\MetaQuest_ObjectDetection\Assets\*.onnx"
```

Verified result:

```text
D:\Robotics design\MetaQuest_ObjectDetection\Assets\PassthroughCameraApiSamples\MultiObjectDetection\SentisInference\Model\yolov9onnx.onnx
```

## 3. Copy the ONNX file to a convenient location

```cmd
copy "D:\Robotics design\MetaQuest_ObjectDetection\Assets\PassthroughCameraApiSamples\MultiObjectDetection\SentisInference\Model\yolov9onnx.onnx" "D:\yolov9onnx.onnx"
```

The `D:\yolov9onnx.onnx` file already contains the ONNX computational graph and stored tensors. For deployment to a compatible inference runtime, **the ONNX file itself is usually sufficient**; exporting separate arrays is optional.

## 4. Install the inspection tools

```cmd
python -m pip install onnx numpy
```

> **Environment warning:** Installing ONNX into the existing Python environment caused reported version conflicts involving TensorFlow, MediaPipe, NumPy, and Protobuf. The inspection succeeded, but other software in that environment may be affected. For a clean environment, use a virtual environment instead:
>
> ```cmd
> cd /d D:\
> python -m venv quest-onnx-env
> quest-onnx-env\Scripts\activate
> python -m pip install onnx numpy
> ```

## 5. Inspect the stored weights directly in CMD

Paste this **single line** into CMD:

```cmd
python -c "import onnx,math,os; p=r'D:\yolov9onnx.onnx'; m=onnx.load(p); w=m.graph.initializer; print('Model size (MiB):',round(os.path.getsize(p)/1024**2,2)); print('ONNX graph nodes:',len(m.graph.node)); print('Initializer tensors:',len(w)); print('Stored scalar values:',sum(math.prod(t.dims) for t in w)); print('First 10 tensors:'); [print(t.name,list(t.dims)) for t in w[:10]]"
```

Observed output:

```text
Model size (MiB): 7.95
ONNX graph nodes: 771
Initializer tensors: 371
Stored scalar values: 2001840
First 10 tensors:
model.0.conv.weight [16, 3, 3, 3]
model.0.conv.bias [16]
model.1.conv.weight [32, 16, 3, 3]
model.1.conv.bias [32]
model.2.cv1.conv.weight [32, 32, 1, 1]
model.2.cv1.conv.bias [32]
model.2.cv2.conv.weight [16, 16, 3, 3]
model.2.cv2.conv.bias [16]
model.2.cv3.conv.weight [16, 16, 3, 3]
model.2.cv3.conv.bias [16]
```

## 6. Export the numerical tensors to a NumPy archive

Paste this **single line** into CMD:

```cmd
python -c "import onnx,numpy as np; from onnx import numpy_helper; m=onnx.load(r'D:\yolov9onnx.onnx'); tensors={w.name:numpy_helper.to_array(w) for w in m.graph.initializer}; np.savez(r'D:\yolov9_weights.npz',**tensors); print('Exported',len(tensors),'tensors to D:\yolov9_weights.npz')"
```

**Output file:** `D:\yolov9_weights.npz`.

Check that the export exists:

```cmd
dir "D:\yolov9_weights.npz"
```

This `.npz` archive stores arrays by tensor name. It is **not** a complete executable model on its own; retain `D:\yolov9onnx.onnx` if you need inference.

## 7. View an exported tensor

```cmd
python -c "import numpy as np; d=np.load(r'D:\yolov9_weights.npz'); print('Tensors:',len(d.files)); x=d['model.0.conv.weight']; print('Shape:',x.shape); print('First 10 values:',x.flatten()[:10])"
```

## 8. APK location and verification status

The build output contained:

```text
D:\Robotics design\MetaQuest_ObjectDetection\Library\Bee\Android\Prj\IL2CPP\Gradle\launcher\build\outputs\apk\release\launcher-release.apk
```

Its observed size was **80,143,565 bytes**. These checks previously returned no matching paths:

```cmd
tar -tf launcher-release.apk | findstr /i "onnx tflite sentis nnmodel"
tar -tf launcher-release.apk | findstr /i "resources.assets sharedassets StreamingAssets"
```

The absence of matching names does **not** establish that the APK lacks model weights. A Unity build may place model data in serialized Unity assets, under different paths, or load it at runtime. To inspect the full APK layout, run this from the APK `release` directory:

```cmd
tar -tf launcher-release.apk | more
```

You can also search for likely Unity data paths:

```cmd
tar -tf launcher-release.apk | findstr /i "assets/bin/Data unity model"
```

**Conclusion:** Source-project weight extraction is confirmed. Byte-for-byte correspondence with the deployed APK model has **not** been verified.

## 9. Transferring the model to the YOR robot

For a robot inference pipeline that supports ONNX, transfer:

```text
D:\yolov9onnx.onnx
```

Before integrating it, independently confirm input size, channel order, normalization, output decoding, class labels, and postprocessing. The model weights alone do not encode all application-level detection settings.

## 10. Key distinction

- **ONNX model (`.onnx`):** computational graph plus stored tensors; preferred for running compatible inference.
- **NumPy archive (`.npz`):** separately exported numeric tensors for inspection or analysis; does not reproduce the full inference graph.
- **APK (`.apk`):** deployable Android package; whether its deployed model matches the discovered ONNX file remains unverified.
