---
name: byted-kickart-overseas-viral-replicator
description: Viral video replication tool that supports copying popular video structures, scripts, and styles to generate similar content. Use this skill when users mention "viral replication, viral cloning, copy video, clone video, similar video" or express the desire to create content similar to a popular video.
version: 1.0.7
---

## 🚨 Pre-validation Process (Must Execute in Order, Terminate on Any Failure)

All user requests must complete the following 2 validation steps in order. Skipping is not allowed:

### 1. Environment Variable Validation
- **Check**: Whether environment variables `KICKART_ACCESS_KEY` and `KICKART_SECRET_KEY` exist
- **If not configured**:
  - Clearly inform the user that Volcengine authentication information is missing
  - **Guide new users to get AK/SK**:
    
    **Script:**
    > ⚠️ Detected that you have not configured Volcengine authentication information
    >
    > For new users:
    > 1️⃣ Visit [kikcart homepage](https://console.byteplus.com/kickart/welcome?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721) to activate your account
    > 2️⃣ Navigate to the [byteplus console](https://console.byteplus.com/iam/keymanage?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721)
    > 3️⃣ Create or retrieve your AccessKey (AK) and SecretKey (SK)
    >
    > After obtaining your credentials, please provide them:
    > 1️⃣ AccessKey (AK)
    > 2️⃣ SecretKey (SK)
  - After obtaining the AK/SK provided by the user, configure it in the system environment variables
  - Continue the process after configuration without requiring manual terminal operations from the user

### 2. Python Dependency Installation
- **Execute command**:
  ```bash
  pip install -r scripts/requirements.txt
  ```
- **If installation fails**:
  - Clearly inform the user of the specific error message
  - Provide solutions (such as upgrading pip, using virtual environments, etc.)
  - Terminate the process until dependencies are successfully installed

## 🎯 Viral Replication Main Process

### 2.0 Intent Confirmation (Mandatory First Step)

#### Trigger Condition
When the user first expresses intent for viral replication (mentions "viral replication, viral cloning, copy video, clone video, similar video" or equivalent expressions)

#### Interaction Script (Mandatory Compliance)

**Script:**
> Do you want to use viral replication to create a video? Reply "yes" to continue.

#### Actions After Success
- **User replies with confirmation** (e.g., "yes", "yeah", "sure", "okay", "confirm", etc.): Proceed to step 2.1 (Get Reference Video)
- **User denies or does not confirm**: Do not proceed with the viral replication process

---

### 2.1 Get Reference Video (Mandatory Second Step)

#### Trigger Condition
After the user has confirmed they want to use viral replication to create a video

#### Video Specifications
- **Format**: Only `MP4` or `MOV` supported
- **Size**: `≤50MB`
- **Duration**: `≤60s`
- **Resolution**: `≥480p`
- **Aspect Ratio**: Supports `9:16`, `16:9`, `3:4`, `4:3`, `1:1`
- **Input Format**: Supports both local file upload and URL

#### Interaction Script (Mandatory Compliance)

**Script:**
> Okay, I'll help you create a viral cloning project. Please first provide the reference video: you can upload a MP4/MOV file (≤60s, ≤50MB, ≥480p) or provide a valid video URL

#### Error Handling
If the video uploaded by the user does not meet the specification requirements, you must clearly point out the exceeded values based on the actual error message:

**Template:**
> This video [metric] [value] exceeds the [limit] limit, please [solution] and send it to me again
Examples:
- `This video size 80MB exceeds the 50MB limit, please compress or use another one and send it to me again`
- `This video duration 90s exceeds the 60s limit, please edit or use another one and send it to me again`
- `This video resolution 360p is below the 480p requirement, please improve clarity or use another one and send it to me again`

#### Actions After Success
- If input is a URL: Download the video to local first, then save the local path as `ref_video`
- If input is a local file: Directly save the local path as `ref_video`
- **Immediately terminate the current round** and wait for the user to reply with product information

---

### 2.2 Get Product Information (Mandatory Third Step)

#### Trigger Condition
After the user has successfully provided the reference video

#### Product Information Requirements
Product information can be provided in one of the following forms (at least one is required):
1. **Product Link** (`product_url`): Any valid product link
2. **Product Images** (`product_images`): Up to 10 images

#### Product Image Specifications
- **Quantity**: `1–10` images
- **Format**: `JPEG` or `PNG`
- **Single Image Size**: `≤8MB`
- **Resolution**: `≥480p`
- **Aspect Ratio**: `> 0.4` and `< 2.5`
- **Minimum Total Pixels**: `300 × 300`
- **Maximum Total Pixels**: `36,000,000` (36 million pixels)
- **Shortest Side**: `≥ 300` pixels
- **Longest Side**: `≤ 6000` pixels
- **Input Format**: Supports both local file upload and URL

#### Interaction Script

**Script:**
> ✅ Reference video received!
>
> Next, please provide product information (at least one is required):
>
> 1️⃣ **Product Link**: Any valid product link
>
> 2️⃣ **Product Images**: Up to 10 images (JPEG/PNG, ≤8MB each, ≥480p), supports uploading files or providing image URLs

#### Rules for Receiving Multiple Product Images
1. **Append Logic**: When the user uploads new product images, **they are appended to the existing product image list by default**, unless the user explicitly states "replace the original images" to overwrite previous IDs
2. **Quantity Limit**:
   - Total quantity limited to maximum 10 images
   - When current list + newly uploaded images total ≤10, all are retained
   - When exceeding 10 images, **clearly inform the user that the 10-image limit has been reached**, and ask the user to choose which 10 to keep, or specify which original images to replace
3. **Order**: All valid product images are arranged in upload order
4. **Proactive Inquiry**: After successfully processing and saving the user's product information, you must proactively inquire about adding more product images:
   - **If user provided only product link (no images)**: Ask if they want to add product images
     
     **Script:**
     > ✅ Product link received!
     >
     > Would you like to add product images? (Up to 10 images, JPEG/PNG, ≤8MB each, ≥480p)
     > You can upload files or provide image URLs. Or reply "skip" / "no need" to proceed to the next step.
     
   - **If user provided product images (<10 images)**: Ask if they want to add more product images
     
     **Script:**
     > ✅ Received {count} product image(s)!
     >
     > Would you like to add more product images? (Current: {count}/10)
     > You can upload files or provide image URLs. Or reply "skip" / "no need" to proceed to the next step.
     
   - **If user provided 10 product images**: Automatically proceed to next step
   - **Only end the image collection phase and proceed to the next step when the user explicitly confirms they don't want to upload more (or the 10-image limit has been reached)**

#### Image Error Handling
If the product image uploaded by the user does not meet the specification requirements, you must clearly point out the specific exceeded values:
```
This image [metric] [value] exceeds the [limit] limit, please [solution] and send it to me again
```
Examples:
- `This image size 12MB exceeds the 8MB limit, please compress or use another one and send it to me again`
- `This image resolution 360p is below the 480p requirement, please improve clarity or use another one and send it to me again`
- `This image aspect ratio 3.0 exceeds the 2.5 limit, please use another one and send it to me again`

#### Actions After Success
- Save the product link as `product_url` (if provided, can be empty string)
- For product images:
  - If input is a URL: Download the image to local first, then save the local path
  - If input is a local file: Directly save the local path
- Save the list of local paths of all product images as `product_images` (in list[str] format, can be empty list)
- **Validation**: At least one of `product_url` or `product_images` must be non-empty
- **Proactive Inquiry Logic**:
  - If user provided only product link (no images): Ask if they want to add product images
  - If user provided product images (<10 images): Ask if they want to add more product images
  - If user provided 10 product images: Proceed to next step (digit avatar images)
  - If user explicitly confirms they don't want to upload more images: Proceed to next step
- **Only proceed to digital avatar images step when**: User has at least one of product_url or product_images, AND user explicitly indicates they don't want to add more product images

---

### 2.3 Get Digital Avatar Images (Mandatory Fourth Step)

#### Digital Avatar Description
- Digital avatars are not required; users can choose not to upload digital avatars, in which case the system will use default digital avatars internally
- Digital avatars must be images

#### Image Specifications
- **Quantity**: `1–3` images
- **Format**: `JPEG` or `PNG`
- **Single Image Size**: `≤10MB`
- **Resolution**: `≥480p`
- **Total Pixels (Width × Height)**: Between `90,000` and `36 million`
- **Aspect Ratio**: Between `0.25` and `4`
- **Avatar Consistency Limitation**: If multiple images are uploaded and the digital human avatars are inconsistent, the system will default to selecting the avatar from the **1st image**
- **Compliance Restrictions**: Uploading celebrity or public IP avatars is strictly prohibited
- **Input Format**: Supports both local file upload and URL

#### Interaction Script

**Script:**
> 💡 I've intelligently matched digital humans for you. If you have custom digital human avatars you'd like to use, you can also send the images directly to me!
>
> ⚠️ **Upload Guidelines**:
> 1️⃣ **Quantity Limit**: Up to 3 images can be uploaded, supports uploading files or providing image URLs;
> 2️⃣ **Avatar Consistency**: If multiple images are uploaded and the avatars are inconsistent, the avatar from the 1st image will be selected by default;
> 3️⃣ **Compliance Requirements**: Please do not upload celebrities, public IPs, or other infringing avatars.

#### Important Specifications (Mandatory Enforcement)
- ❌ **Prohibited from Using Other Scripts**: Do not use inquiry-style scripts such as "Would you like to add a custom model"; must use the standard script above
- ❌ **Prohibited from Mentioning Size Requirements**: Do not mention specific size requirements like "500*500px"; adhere to the specifications in the guidelines
- ❌ **Prohibited from Using Urging Language**: Do not include urging expressions like "continue to the next step" in the script

#### Rules for Receiving Multiple Images
1. **Append Logic**: When the user uploads new digital avatar images, **they are appended to the existing digital avatar list by default**, unless the user explicitly states "replace the original avatar" to overwrite previous IDs
2. **Quantity Limit**:
   - Total quantity limited to maximum 3 images
   - When current list + newly uploaded images total ≤3, all are retained
   - When exceeding 3 images, **clearly inform the user that the 3-image limit has been reached**, and ask the user to choose which 3 to keep, or specify which original images to replace
3. **Order**: All valid avatars are arranged in upload order, with the first being the default digital avatar to use
4. **Proactive Inquiry**: After successfully processing and saving the user's digital avatar images, you must proactively inquire about adding more avatar images:
   - **If user provided avatar images (<3 images)**: Ask if they want to add more avatar images
     ```
     ✅ Received {count} digital avatar image(s)!
     
     Would you like to add more avatar images? (Current: {count}/3)
     You can upload files or provide image URLs. Or reply "skip" / "no need" to proceed to language selection.
     ```
   - **If user uploaded no avatars (user replied "skip" to initial prompt)**: Proceed to language selection (Step 2.4)
   - **If user provided 3 avatar images**: Automatically proceed to next step (language selection)
   - **Only end the avatar collection phase and proceed to Step 2.4 (Select Video Language) when the user explicitly confirms they don't want to upload more (or the 3-image limit has been reached)**

#### Error Handling
If the image uploaded by the user does not meet the specification requirements, you must clearly point out the specific exceeded values:
```
This image [metric] [value] exceeds the [limit] limit, please [solution] and send it to me again
```
Examples:
- `This image size 15MB exceeds the 10MB limit, please compress or use another one and send it to me again`
- `This image resolution 360p is below the 480p requirement, please improve clarity or use another one and send it to me again`

#### Actions After Success
- For digital avatar images:
  - If input is a URL: Download the image to local first, then save the local path
  - If input is a local file: Directly save the local path
- Save the list of local paths of all digital avatar images as `model_images` (in list[str] format)
- If no digital avatars were uploaded, this should be an empty list `[]`
- **Next Step Logic** (CRITICAL):
  - ✅ **After user uploads avatars** (any count < 3): Ask if they want to add more avatar images
  - ✅ **After user uploads 3 avatars**: Automatically proceed to Step 2.4 (Select Video Language)
  - ✅ **After user replies "skip" / "no need"** (either to initial prompt or follow-up inquiry): **MUST proceed to Step 2.4 (Select Video Language)**
  - ✅ **After user explicitly confirms no more images**: Proceed to Step 2.4 (Select Video Language)
- **NEVER skip Step 2.4 (Select Video Language)**: The language selection step must always be executed after avatar collection, even if the user uploaded no avatars

---

### 2.4 Select Video Language (Optional Configuration)

#### Language Description
- **Default**: English (en) - British English
- **Supported Languages**: Users can customize the video language, which affects voiceover, subtitles, and other language-related elements

#### Supported Language List
- `zh`: Chinese (简体中文)
- `en`: English (British) - Default
- `en-us`: English (American)
- `pt-br`: Portuguese (Brazilian)
- `ja`: Japanese
- `es-mx`: Spanish (Mexican)
- `id`: Indonesian
- `ms`: Malay
- `tl`: Filipino

#### Trigger Condition
**After completing Step 2.3 (Get Digital Avatar Images), regardless of whether avatars were uploaded:**
- User uploaded avatar images (and confirmed no more images)
- User uploaded 3 avatar images (auto-proceed)
- User replied "skip" / "no need" to avatar upload prompt

#### Interaction Script

**Script:**
> 🎯 Next, please select the video language (optional, default is English):
> - zh: Chinese (简体中文)
> - en: English (British) - Default
> - en-us: English (American)
> - pt-br: Portuguese (Brazilian)
> - ja: Japanese
> - es-mx: Spanish (Mexican)
> - id: Indonesian
> - ms: Malay
> - tl: Filipino
>
> 👉 Reply with the language code (e.g., "zh" for Chinese), or reply "skip" to use English by default

**Note**: 
- If user uploaded avatars in previous step, you may prepend "✅ Digital avatar images received!" before the language selection script
- If user skipped avatar upload (replied "skip"), do NOT mention avatar images - directly show the language selection script

#### Actions After Success
- Save the selected language as `language` (defaults to "en" if not specified)
- **Immediately terminate the current round** and proceed to compliance commitment

---

### 2.5 Compliance Commitment (Mandatory Confirmation)

#### Trigger Condition
After the user has provided all necessary information (reference video, product information, digital avatar images)

#### Compliance Commitment Template (Mandatory Use, Preserve Line Breaks)

**Script:**
> 💡 This task will consume creation points. Once the task is initiated, creation points consumed cannot be refunded.
> Please confirm that you have read and agreed to [Authorization Statement](https://docs.byteplus.com/en/docs/kickart/Authorization_Statement?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721) and [Virtual Avatar Compliance Commitment](https://docs.byteplus.com/en/docs/kickart/Virtual_Avatar_Compliance_Commitment?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721).
>
>  Reply to confirm, and I will immediately start creating the video for you~

#### Mandatory Requirements
- ✅ The user must explicitly reply with agreement (such as "confirm", "agree", "okay", etc.) to continue the task
- ❌ If the user does not explicitly reply with agreement, consider the task abandoned and do not submit

---

### 2.6 Submit Viral Replication Task

#### Execute Script
```bash
python scripts/kickart.py submit --params '<JSON string>'
```

#### Parameter Requirements
The `--params` parameter must be in JSON string format, containing the following fields:

```json
{
  "ref_video": "string",       // Required, local path of reference video from 2.1
  "product_url": "string",     // Optional, product link from 2.2 (can be empty string)
  "product_images": ["string"],// Optional, list of local paths of product images from 2.2 (can be empty list)
  "model_images": ["string"],  // Required, list of local paths of digital avatar images from 2.3
  "language": "string"         // Optional, video language from 2.4 (defaults to "en")
}
```

**Note**: At least one of `product_url` or `product_images` must be non-empty.

#### Return Value
Returns JSON format data containing:
- `task_id`: Task ID, used to query task results later

---

### 2.7 Task Query and Feedback

#### Query Command
```bash
python scripts/kickart.py query --task_id <Task ID>
```

#### Parameter Requirements
- `task_id`: String format, fill in the task_id returned from 2.5 (Submit Viral Replication Task)

#### Return Fields
- `task_id`: Task ID
- `task_status`: Task status (RUNNING/SUCCESS/FAILED)
- `payload`: Task detailed information
  - `result_url`: Final video URL generated by viral replication

---

#### 2.7.1 Task Success Reply Template

**Script:**
> ✅ Viral replication task submitted successfully, Task ID:<Task ID>
> ⚠️ The task is executing in the background. You can check the progress at any time using "Check Progress" to get the latest status~ 🦞

---

#### 2.7.2 Task Failure Reply Template

**Mandatory Requirements:**
- MUST use the exact error message returned by the platform (including all markdown links)
- NEVER modify, truncate, or omit any part of the error message
- If the error message contains links (e.g., `[text](url)`), they MUST be preserved exactly as returned

**Reply Template:**
> ❌ Viral replication task submission failed (Task ID:<Task ID>)
> - Error Code: <Error code from platform>
> - Error Message: <Complete error message from platform, with all links preserved>
>
> <Optional: Additional context-specific guidance based on the error>

**Examples:**

For insufficient credits (code 1402):
> ❌ Viral replication task submission failed (Task ID:abc123)
> - Error Code: 1402
> - Error Message: Insufficient Credits! Your account balance is insufficient to cover the cost of this task. Please top up your account in [kikcart homepage](https://console.byteplus.com/kickart/welcome?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721).
>
> Once the account is topped up, I can submit the same task again immediately.

For authorization required (code 100013):
>  Viral replication task submission failed (Task ID:abc123)
> - Error Code: 100013
> - Error Message: You are not authorized to perform this operation. Please contact your enterprise administrator to grant permissions, or visit [Kickart Plan Page](https://console.byteplus.com/kickart/setting/combobuy?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721) to subscribe to a plan.

For invalid AccessKey (code 100009):
> ❌ Viral replication task submission failed (Task ID:abc123)
> - Error Code: 100009
> - Error Message: The AccessKey included in the request is invalid. Please check your AccessKey in [Byteplus Console](https://console.byteplus.com/iam/keymanage?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721).

---

#### 2.7.3 Task Execution Polling Rules

- **Polling Frequency**: Query task progress every 30 seconds
- **Notify User**: Notify the user of task progress after each query
- **Polling Limit**: Maximum 120 polls (approximately 60 minutes)
- **Termination Conditions**:
  - Task status becomes SUCCESS: Stop polling, display success message
  - Task status becomes FAILED: Stop polling, display failure message
  - Reach polling limit: Inform the user that the task is still executing and suggest checking later

#### Progress Notification Template

**Script:**
> 📊 Task Progress Update (Task ID:<Task ID>)
> Current Status:<Task Status>
> Estimated Remaining Time:<Display if available>

---

##  Strict Prohibitions

1. **Prohibited from Skipping Steps**: Must strictly follow the order 2.0 → 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6. Cannot proceed to the next step if any step is incomplete
2. **Prohibited from Merging Steps**: Each step must be confirmed separately with the user. Cannot collect multiple pieces of information in a single conversation
3. **Prohibited from Early Execution**: Cannot execute the next step before the user has explicitly confirmed the previous step's information
4. **Prohibited from Omitting Compliance Commitment**: Section 2.5 Compliance Commitment is a mandatory step and cannot be omitted for any reason
5. **Prohibited from Omitting Intent Confirmation**: Section 2.0 Intent Confirmation is a mandatory step and cannot be omitted for any reason
6. **Prohibited from Unauthorized Script Modifications**: All scripts marked as "Mandatory Compliance" must be used strictly according to the original text without unauthorized modifications
7. **Prohibited from Accepting Unsupported Product Links** (CRITICAL):
   - MUST validate all product links against supported platforms (Amazon, Ebay, Mercado Livre)
   - MUST reject links from unsupported platforms (TikTok Shop, Shopee, AliExpress, Temu, etc.)
   - MUST provide clear error message directing users to supported platforms
   - NEVER accept a product link without first validating its domain

---

## 🔧 Technical Implementation Details

### Environment Variable Reading
```python
import os
ak = os.getenv("KICKART_ACCESS_KEY", "")
sk = os.getenv("KICKART_SECRET_KEY", "")
if not ak or not sk:
    # Prompt user to configure environment variables
```

### Dependency Installation
```bash
pip install -r requirements.txt
```

**Note**: The scripts use the `filetype` library for MIME type detection, which identifies file types by reading their magic bytes (file signatures). This approach:
- Does NOT require any system-level dependencies (like libmagic)
- Works cross-platform without additional installation steps
- Provides fast and reliable file type detection based on actual file content

### Product Link Validation

**IMPORTANT**: All product links MUST be validated before acceptance. Reference implementation:

```python
from urllib.parse import urlparse

def validate_product_link(url: str) -> tuple[bool, str]:
    """Validate if product link is from supported platforms."""
    if not url:
        return (True, "")  # Empty URL is OK if product images provided
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Supported platforms
        supported_domains = [
            'amazon.',      # amazon.com, amazon.co.uk, amazon.de, etc.
            'ebay.',        # ebay.com, ebay.co.uk, ebay.de, etc.
            'mercadolivre.', # mercadolivre.com.br
            'mercadolibre.', # mercadolibre.com.mx, mercadolibre.com.ar, etc.
        ]
        
        for supported in supported_domains:
            if supported in domain:
                return (True, "")
        
        # Unsupported platform - reject
        return (False, "Unsupported platform")
        
    except Exception as e:
        return (False, f"Invalid URL: {str(e)}")
```

**Supported Platforms**:
- ✅ **Amazon**: Any domain containing `amazon.`
- ✅ **Ebay**: Any domain containing `ebay.`
- ✅ **Mercado Livre**: Any domain containing `mercadolivre.` or `mercadolibre.`
- ❌ **All others**: Must be rejected

### Task Submission Example

**With Product Link (Default English) - Amazon:**
```bash
python scripts/kickart.py submit --params '{"ref_video":"/path/to/video.mp4","product_url":"https://www.amazon.com/dp/B08N5WRWNW","product_images":[],"model_images":["/path/to/image1.jpg","/path/to/image2.jpg"],"language":"en"}'
```

**With Product Link - Ebay:**
```bash
python scripts/kickart.py submit --params '{"ref_video":"/path/to/video.mp4","product_url":"https://www.ebay.com/itm/123456789","product_images":[],"model_images":["/path/to/image1.jpg"],"language":"en"}'
```

**With Product Link - Mercado Livre:**
```bash
python scripts/kickart.py submit --params '{"ref_video":"/path/to/video.mp4","product_url":"https://mercadolivre.com.br/produto-123","product_images":[],"model_images":["/path/to/image1.jpg"],"language":"pt-br"}'
```

**With Product Images (Chinese):**
```bash
python scripts/kickart.py submit --params '{"ref_video":"/path/to/video.mp4","product_url":"","product_images":["/path/to/product1.jpg","/path/to/product2.jpg"],"model_images":["/path/to/image1.jpg"],"language":"zh"}'
```

**With Both Product Link and Images (Portuguese - Brazil):**
```bash
python scripts/kickart.py submit --params '{"ref_video":"/path/to/video.mp4","product_url":"https://www.amazon.com.br/dp/xxxxx","product_images":["/path/to/product1.jpg"],"model_images":["/path/to/image1.jpg"],"language":"pt-br"}'
```

### Task Query Example
```bash
python scripts/kickart.py query --task_id "abc123def456"
```

---

## 📞 User Support

If you encounter issues, please get help through the following channels:
- View official documentation: https://www.volcengine.com/docs/6664/
- Contact technical support: support@volcengine.com