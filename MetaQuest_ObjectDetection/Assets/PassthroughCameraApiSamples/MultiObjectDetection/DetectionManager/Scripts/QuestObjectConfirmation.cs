using System;
using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace PassthroughCameraSamples.MultiObjectDetection
{
    public class QuestObjectConfirmation : MonoBehaviour
    {
        // ============================================================
        // WINDOWS OBJECT MEMORY SERVER
        // ============================================================

        [Header("Windows Object Memory Server")]
        [SerializeField]
        private string memoryServerBaseUrl =
            "http://172.25.230.76:8000";


        // ============================================================
        // CONFIRMATION UI
        // ============================================================

        [Header("Confirmation UI")]

        [SerializeField]
        private GameObject confirmationPanel;

        [SerializeField]
        private RawImage objectImage;

        [SerializeField]
        private TMP_Text questionText;


        // ============================================================
        // DEBUG
        //
        // Keep this FALSE.
        //
        // Normal behavior:
        //   Quest starts
        //   -> no confirmation panel
        //   -> user presses X
        //   -> search starts
        // ============================================================

        [Header("Debug Test")]

        [SerializeField]
        private bool autoTestCup = false;


        // ============================================================
        // OBJECT RECORD RETURNED BY SERVER
        // ============================================================

        [Serializable]
        public class ObjectRecord
        {
            public int id;

            public string observation_id;

            public string label;

            public float confidence;

            public float quest_x;
            public float quest_y;
            public float quest_z;

            public string full_image_url;
            public string crop_image_url;
            public string image_url;
        }


        // ============================================================
        // RESPONSE FROM:
        //
        // GET /objects/search?label=cup
        // ============================================================

        [Serializable]
        public class SearchResponse
        {
            public string label;

            public int count;

            public List<ObjectRecord> objects;
        }


        // ============================================================
        // CONFIRMATION JSON SENT TO SERVER
        // ============================================================

        [Serializable]
        private class ConfirmationRequest
        {
            public bool confirmed;
        }


        // ============================================================
        // RUNTIME STATE
        // ============================================================

        private List<ObjectRecord> candidates =
            new List<ObjectRecord>();

        private int currentIndex = 0;

        // True while Quest is querying the object database.
        private bool searchInProgress = false;

        // True while YES or NO is currently being handled.
        //
        // This prevents:
        // YES
        // YES
        // YES
        //
        // from sending multiple requests.
        private bool confirmationActionInProgress = false;


        // ============================================================
        // STARTUP
        // ============================================================

        private IEnumerator Start()
        {
            // --------------------------------------------------------
            // Confirmation panel must be hidden when app starts.
            // --------------------------------------------------------

            if (confirmationPanel != null)
            {
                confirmationPanel.SetActive(false);
            }


            // --------------------------------------------------------
            // Clear any old texture.
            // --------------------------------------------------------

            if (objectImage != null)
            {
                objectImage.texture = null;
            }


            // --------------------------------------------------------
            // Normal operation stops here.
            //
            // The user must press X to search.
            // --------------------------------------------------------

            if (!autoTestCup)
            {
                yield break;
            }


            // --------------------------------------------------------
            // Optional debugging only.
            // --------------------------------------------------------

            yield return new WaitForSeconds(3f);


            Debug.Log(
                "DEBUG_CONFIRMATION_TEST: Searching for cup"
            );


            FindObject("cup");
        }


        // ============================================================
        // CONTROLLER INPUT
        // ============================================================

        private void Update()
        {
            // ========================================================
            // LEFT CONTROLLER X BUTTON
            //
            // TEMPORARY SEARCH COMMAND:
            //
            // X -> search database for "cup"
            //
            // Later this can be replaced by:
            // - text input
            // - voice recognition
            // ========================================================

            if (
                OVRInput.GetDown(
                    OVRInput.RawButton.X
                )
            )
            {
                Debug.Log(
                    "SEARCH_INPUT: X BUTTON -> FIND CUP"
                );


                // Do not start another search while one is running.
                if (searchInProgress)
                {
                    Debug.Log(
                        "SEARCH_INPUT_IGNORED: " +
                        "Search already in progress."
                    );

                    return;
                }


                // Do not interrupt a YES/NO operation.
                if (confirmationActionInProgress)
                {
                    Debug.Log(
                        "SEARCH_INPUT_IGNORED: " +
                        "Confirmation action in progress."
                    );

                    return;
                }


                FindObject("cup");

                return;
            }


            // ========================================================
            // YES / NO are only valid while a candidate is shown.
            // ========================================================

            if (
                confirmationPanel == null ||
                !confirmationPanel.activeSelf ||
                candidates == null ||
                candidates.Count == 0 ||
                currentIndex >= candidates.Count
            )
            {
                return;
            }


            // ========================================================
            // Prevent repeated trigger presses while processing.
            // ========================================================

            if (confirmationActionInProgress)
            {
                return;
            }


            // ========================================================
            // RIGHT INDEX TRIGGER = YES
            // ========================================================

            if (
                OVRInput.GetDown(
                    OVRInput.Button.SecondaryIndexTrigger
                )
            )
            {
                Debug.Log(
                    "CONFIRM_INPUT: RIGHT TRIGGER = YES"
                );


                ConfirmYes();

                return;
            }


            // ========================================================
            // LEFT INDEX TRIGGER = NO
            // ========================================================

            if (
                OVRInput.GetDown(
                    OVRInput.Button.PrimaryIndexTrigger
                )
            )
            {
                Debug.Log(
                    "CONFIRM_INPUT: LEFT TRIGGER = NO"
                );


                ConfirmNo();
            }
        }


        // ============================================================
        // PUBLIC SEARCH FUNCTION
        //
        // Current:
        //
        //     FindObject("cup")
        //
        // Future text:
        //
        //     FindObject(textInput)
        //
        // Future voice:
        //
        //     FindObject(recognizedObjectName)
        // ============================================================

        public void FindObject(
            string label)
        {
            // --------------------------------------------------------
            // Validate label.
            // --------------------------------------------------------

            if (
                string.IsNullOrWhiteSpace(
                    label
                )
            )
            {
                Debug.LogWarning(
                    "FIND_OBJECT_FAILED: Empty label."
                );

                return;
            }


            // --------------------------------------------------------
            // Prevent parallel searches.
            // --------------------------------------------------------

            if (searchInProgress)
            {
                Debug.LogWarning(
                    "FIND_OBJECT_FAILED: " +
                    "Another search is already running."
                );

                return;
            }


            if (confirmationActionInProgress)
            {
                Debug.LogWarning(
                    "FIND_OBJECT_FAILED: " +
                    "Confirmation action is currently running."
                );

                return;
            }


            // --------------------------------------------------------
            // Clean search label.
            // --------------------------------------------------------

            string cleanLabel =
                label.Trim().ToLower();


            // --------------------------------------------------------
            // Clear any old candidate state.
            // --------------------------------------------------------

            candidates.Clear();

            currentIndex = 0;


            if (objectImage != null)
            {
                objectImage.texture = null;
            }


            if (confirmationPanel != null)
            {
                confirmationPanel.SetActive(false);
            }


            Debug.Log(
                $"QUEST_SEARCH_START: [{cleanLabel}]"
            );


            StartCoroutine(
                SearchDatabase(
                    cleanLabel
                )
            );
        }


        // ============================================================
        // SEARCH WINDOWS DATABASE
        // ============================================================

        private IEnumerator SearchDatabase(
            string label)
        {
            searchInProgress = true;


            // --------------------------------------------------------
            // Build server URL.
            // --------------------------------------------------------

            string baseUrl =
                memoryServerBaseUrl.TrimEnd('/');


            string url =
                baseUrl +
                "/objects/search?label=" +
                UnityWebRequest.EscapeURL(
                    label
                );


            Debug.Log(
                $"QUEST_SEARCH_URL: {url}"
            );


            using (
                UnityWebRequest request =
                    UnityWebRequest.Get(
                        url
                    )
            )
            {
                request.timeout = 5;


                yield return
                    request.SendWebRequest();


                // ====================================================
                // SERVER SEARCH FAILED
                // ====================================================

                if (
                    request.result !=
                    UnityWebRequest.Result.Success
                )
                {
                    searchInProgress = false;


                    Debug.LogError(
                        "QUEST_SEARCH_FAILED: " +
                        $"HTTP={request.responseCode}, " +
                        $"Error={request.error}, " +
                        $"Response={request.downloadHandler.text}"
                    );


                    // Show a short error message.
                    if (confirmationPanel != null)
                    {
                        confirmationPanel.SetActive(true);
                    }


                    if (questionText != null)
                    {
                        questionText.text =
                            "Database search failed.";
                    }


                    yield return
                        new WaitForSeconds(1.2f);


                    HideConfirmationUI();


                    yield break;
                }


                // ====================================================
                // SERVER SEARCH SUCCEEDED
                // ====================================================

                string json =
                    request.downloadHandler.text;


                Debug.Log(
                    "QUEST_SEARCH_RESPONSE: " +
                    json
                );


                SearchResponse response =
                    JsonUtility.FromJson<SearchResponse>(
                        json
                    );


                // ====================================================
                // NO MATCHING OBJECTS
                // ====================================================

                if (
                    response == null ||
                    response.objects == null ||
                    response.objects.Count == 0
                )
                {
                    searchInProgress = false;


                    candidates.Clear();

                    currentIndex = 0;


                    if (objectImage != null)
                    {
                        objectImage.texture = null;
                    }


                    if (confirmationPanel != null)
                    {
                        confirmationPanel.SetActive(true);
                    }


                    if (questionText != null)
                    {
                        questionText.text =
                            $"No saved {label} images found.";
                    }


                    Debug.LogWarning(
                        $"NO_OBJECT_MEMORY: [{label}]"
                    );


                    yield return
                        new WaitForSeconds(1.2f);


                    HideConfirmationUI();


                    yield break;
                }


                // ====================================================
                // STORE CANDIDATES
                // ====================================================

                candidates =
                    response.objects;


                currentIndex = 0;


                Debug.Log(
                    "OBJECT_CANDIDATES_FOUND: " +
                    $"Label=[{label}], " +
                    $"Count={candidates.Count}"
                );


                // ----------------------------------------------------
                // Now show confirmation panel.
                // ----------------------------------------------------

                if (confirmationPanel != null)
                {
                    confirmationPanel.SetActive(true);
                }


                // ----------------------------------------------------
                // Display first candidate.
                // ----------------------------------------------------

                yield return
                    ShowCurrentObject();


                searchInProgress = false;
            }
        }


        // ============================================================
        // DISPLAY CURRENT CANDIDATE
        // ============================================================

        private IEnumerator ShowCurrentObject()
        {
            // --------------------------------------------------------
            // Candidate validation.
            // --------------------------------------------------------

            if (
                candidates == null ||
                candidates.Count == 0 ||
                currentIndex >= candidates.Count
            )
            {
                if (objectImage != null)
                {
                    objectImage.texture = null;
                }


                if (questionText != null)
                {
                    questionText.text =
                        "No more matching objects.";
                }


                Debug.Log(
                    "NO_MORE_OBJECT_CANDIDATES"
                );


                yield return
                    new WaitForSeconds(1.2f);


                HideConfirmationUI();


                yield break;
            }


            ObjectRecord obj =
                candidates[currentIndex];


            Debug.Log(
                "SHOW_OBJECT_CANDIDATE: " +
                $"Index={currentIndex}, " +
                $"Observation={obj.observation_id}, " +
                $"Label=[{obj.label}]"
            );


            // --------------------------------------------------------
            // Clear old image first.
            // --------------------------------------------------------

            if (objectImage != null)
            {
                objectImage.texture = null;
            }


            if (questionText != null)
            {
                questionText.text =
                    $"Loading {obj.label}...";
            }


            // ========================================================
            // NO IMAGE URL
            // ========================================================

            if (
                string.IsNullOrEmpty(
                    obj.image_url
                )
            )
            {
                Debug.LogWarning(
                    "OBJECT_HAS_NO_IMAGE: " +
                    obj.observation_id
                );


                if (questionText != null)
                {
                    questionText.text =
                        "This object has no stored image.";
                }


                yield return
                    new WaitForSeconds(1.0f);


                yield break;
            }


            // ========================================================
            // BUILD IMAGE URL
            // ========================================================

            string imageUrl =
                memoryServerBaseUrl.TrimEnd('/') +
                obj.image_url;


            Debug.Log(
                "QUEST_IMAGE_DOWNLOAD: " +
                imageUrl
            );


            // ========================================================
            // DOWNLOAD IMAGE
            // ========================================================

            using (
                UnityWebRequest request =
                    UnityWebRequestTexture.GetTexture(
                        imageUrl
                    )
            )
            {
                request.timeout = 10;


                yield return
                    request.SendWebRequest();


                // ----------------------------------------------------
                // Download failed.
                // ----------------------------------------------------

                if (
                    request.result !=
                    UnityWebRequest.Result.Success
                )
                {
                    Debug.LogError(
                        "QUEST_IMAGE_FAILED: " +
                        $"HTTP={request.responseCode}, " +
                        $"Error={request.error}"
                    );


                    if (questionText != null)
                    {
                        questionText.text =
                            "Failed to download object image.";
                    }


                    yield break;
                }


                // ----------------------------------------------------
                // Download succeeded.
                // ----------------------------------------------------

                Texture2D texture =
                    DownloadHandlerTexture.GetContent(
                        request
                    );


                if (objectImage != null)
                {
                    objectImage.texture =
                        texture;
                }


                if (questionText != null)
                {
                    questionText.text =
                        $"Is this your {obj.label}?";
                }


                Debug.Log(
                    "QUEST_IMAGE_DISPLAYED: " +
                    $"Observation={obj.observation_id}, " +
                    $"Size={texture.width}x{texture.height}"
                );
            }
        }


        // ============================================================
        // USER SELECTS YES
        //
        // RIGHT INDEX TRIGGER
        // ============================================================

        public void ConfirmYes()
        {
            // --------------------------------------------------------
            // Validate candidate.
            // --------------------------------------------------------

            if (
                candidates == null ||
                candidates.Count == 0 ||
                currentIndex >= candidates.Count
            )
            {
                Debug.LogWarning(
                    "CONFIRM_YES_FAILED: " +
                    "No active candidate."
                );

                return;
            }


            // --------------------------------------------------------
            // Prevent duplicate requests.
            // --------------------------------------------------------

            if (confirmationActionInProgress)
            {
                Debug.Log(
                    "CONFIRM_YES_IGNORED: " +
                    "Confirmation already in progress."
                );

                return;
            }


            confirmationActionInProgress = true;


            ObjectRecord selected =
                candidates[currentIndex];


            Debug.Log(
                "QUEST_USER_YES: " +
                $"Observation={selected.observation_id}, " +
                $"Label=[{selected.label}]"
            );


            // --------------------------------------------------------
            // Immediately give user feedback.
            // --------------------------------------------------------

            if (questionText != null)
            {
                questionText.text =
                    "Sending to YOR...";
            }


            // --------------------------------------------------------
            // Send confirmation to Windows server.
            // --------------------------------------------------------

            StartCoroutine(
                SendConfirmation(
                    selected
                )
            );
        }


        // ============================================================
        // USER SELECTS NO
        //
        // LEFT INDEX TRIGGER
        // ============================================================

        public void ConfirmNo()
        {
            // --------------------------------------------------------
            // Validate candidate.
            // --------------------------------------------------------

            if (
                candidates == null ||
                candidates.Count == 0 ||
                currentIndex >= candidates.Count
            )
            {
                Debug.LogWarning(
                    "CONFIRM_NO_FAILED: " +
                    "No active candidate."
                );

                return;
            }


            // --------------------------------------------------------
            // Prevent multiple NO actions.
            // --------------------------------------------------------

            if (confirmationActionInProgress)
            {
                Debug.Log(
                    "CONFIRM_NO_IGNORED: " +
                    "Another confirmation action is running."
                );

                return;
            }


            confirmationActionInProgress = true;


            StartCoroutine(
                HandleNoSelection()
            );
        }


        // ============================================================
        // HANDLE NO
        // ============================================================

        private IEnumerator HandleNoSelection()
        {
            ObjectRecord rejected =
                candidates[currentIndex];


            Debug.Log(
                "QUEST_USER_NO: " +
                $"Observation={rejected.observation_id}, " +
                $"Label=[{rejected.label}]"
            );


            // --------------------------------------------------------
            // Tell user we are looking for another candidate.
            // --------------------------------------------------------

            if (questionText != null)
            {
                questionText.text =
                    "Searching the database for more...";
            }


            // --------------------------------------------------------
            // Remove rejected image from display.
            // --------------------------------------------------------

            if (objectImage != null)
            {
                objectImage.texture = null;
            }


            Debug.Log(
                "SEARCHING_NEXT_OBJECT_CANDIDATE"
            );


            // --------------------------------------------------------
            // Brief status delay.
            // --------------------------------------------------------

            yield return
                new WaitForSeconds(0.8f);


            // --------------------------------------------------------
            // Move to next candidate.
            // --------------------------------------------------------

            currentIndex++;


            // ========================================================
            // NO MORE MATCHING OBJECTS
            // ========================================================

            if (
                currentIndex >=
                candidates.Count
            )
            {
                if (questionText != null)
                {
                    questionText.text =
                        "No more matching objects.";
                }


                Debug.Log(
                    "NO_MORE_OBJECT_CANDIDATES"
                );


                // Let user read message.
                yield return
                    new WaitForSeconds(1.2f);


                // Hide everything.
                HideConfirmationUI();


                yield break;
            }


            // ========================================================
            // ANOTHER CANDIDATE EXISTS
            // ========================================================

            Debug.Log(
                "NEXT_OBJECT_CANDIDATE_FOUND: " +
                $"Index={currentIndex}"
            );


            // --------------------------------------------------------
            // Show next stored object.
            // --------------------------------------------------------

            yield return
                ShowCurrentObject();


            // --------------------------------------------------------
            // Allow triggers again.
            // --------------------------------------------------------

            confirmationActionInProgress = false;
        }


        // ============================================================
        // SEND YES CONFIRMATION TO WINDOWS SERVER
        //
        // The server then queues the object retrieval task for YOR.
        // ============================================================

        private IEnumerator SendConfirmation(
            ObjectRecord obj)
        {
            // --------------------------------------------------------
            // JSON request body.
            // --------------------------------------------------------

            ConfirmationRequest body =
                new ConfirmationRequest
                {
                    confirmed = true
                };


            string json =
                JsonUtility.ToJson(
                    body
                );


            // --------------------------------------------------------
            // Build confirm endpoint.
            // --------------------------------------------------------

            string url =
                memoryServerBaseUrl.TrimEnd('/') +
                "/objects/" +
                obj.observation_id +
                "/confirm";


            Debug.Log(
                $"QUEST_CONFIRM_URL: {url}"
            );


            Debug.Log(
                $"QUEST_CONFIRM_JSON: {json}"
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


                // ====================================================
                // YES CONFIRMATION SUCCEEDED
                // ====================================================

                if (
                    request.result ==
                    UnityWebRequest.Result.Success
                )
                {
                    Debug.Log(
                        "QUEST_CONFIRM_OK: " +
                        request.downloadHandler.text
                    );


                    // ------------------------------------------------
                    // Tell user that task was sent.
                    // ------------------------------------------------

                    if (questionText != null)
                    {
                        questionText.text =
                            "Sent to YOR.";
                    }


                    // ------------------------------------------------
                    // Let user read the message.
                    // ------------------------------------------------

                    yield return
                        new WaitForSeconds(1.2f);


                    // ------------------------------------------------
                    // Close confirmation screen.
                    // ------------------------------------------------

                    HideConfirmationUI();
                }

                // ====================================================
                // YES CONFIRMATION FAILED
                // ====================================================

                else
                {
                    Debug.LogError(
                        "QUEST_CONFIRM_FAILED: " +
                        $"HTTP={request.responseCode}, " +
                        $"Error={request.error}, " +
                        $"Response=" +
                        request.downloadHandler.text
                    );


                    if (questionText != null)
                    {
                        questionText.text =
                            "Failed to send to YOR. Try again.";
                    }


                    // Allow another trigger attempt.
                    confirmationActionInProgress = false;
                }
            }
        }


        // ============================================================
        // HIDE AND RESET CONFIRMATION UI
        // ============================================================

        private void HideConfirmationUI()
        {
            // --------------------------------------------------------
            // Remove image.
            // --------------------------------------------------------

            if (objectImage != null)
            {
                objectImage.texture = null;
            }


            // --------------------------------------------------------
            // Hide complete confirmation panel.
            // --------------------------------------------------------

            if (confirmationPanel != null)
            {
                confirmationPanel.SetActive(false);
            }


            // --------------------------------------------------------
            // Reset candidate list.
            // --------------------------------------------------------

            if (candidates != null)
            {
                candidates.Clear();
            }


            currentIndex = 0;

            searchInProgress = false;

            confirmationActionInProgress = false;


            Debug.Log(
                "CONFIRMATION_UI_HIDDEN"
            );
        }
    }
}