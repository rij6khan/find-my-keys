# Find My Keys

Socially Cognizant Robotics project for remembering and retrieving objects with a Meta Quest headset and the YOR robot.

## Components

- [`MetaQuest_ObjectDetection`](./MetaQuest_ObjectDetection/) — Unity/Quest passthrough-camera object detection, confirmation UI, image capture, and object-memory client.
- [`QuestObjectMemory`](./QuestObjectMemory/) — FastAPI and SQLite object-memory service, including the current sample database and images.
- [`FindRetrieveKeys`](./FindRetrieveKeys/) — companion Unity project.
- [`nav`](./nav/) — robot localization utilities.

See each component's README or setup document for its own requirements and run instructions.
