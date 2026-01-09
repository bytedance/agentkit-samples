/**
 * Multimodal client for handling webcam/screen video and audio streaming to Gemini Live API
 */

class StreamManager extends SoundHandler {
    constructor(serverUrl = 'wss://adk-audio-assistant-234439745674.us-central1.run.app') {
        super(serverUrl);

        // Video streaming properties
        this.videoStream = null;
        this.videoElement = null;
        this.isVideoActive = false;
        this.videoSendInterval = null;
        this.videoFrameRate = 1; // Send 1 frame per second by default
        this.videoMode = null; // 'webcam' or 'screen'
        this.screenTrack = null;

        // Override reconnection settings from parent class
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 0; // Prevent automatic reconnection
        this.isReconnecting = false;
    }

    // Initialize webcam
    async setupWebcam(videoElement) {
        if (!videoElement) {
            console.error('Video element is required');
            return false;
        }

        // First, clean up any existing streams
        this.stopVideo();

        this.videoElement = videoElement;
        this.videoMode = 'webcam';

        try {
            // Request camera access
            this.videoStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                }
            });

            // Set video element source
            this.videoElement.srcObject = this.videoStream;
            this.isVideoActive = true;

            return true;
        } catch (error) {
            console.error('Error setting up webcam:', error);
            return false;
        }
    }

    // Initialize screen sharing
    async setupScreenShare(videoElement) {
        if (!videoElement) {
            console.error('Video element is required');
            return false;
        }

        // First, clean up any existing streams
        this.stopVideo();

        this.videoElement = videoElement;
        this.videoMode = 'screen';

        try {
            // Request screen sharing access
            this.videoStream = await navigator.mediaDevices.getDisplayMedia({
                video: {
                    cursor: "always"
                },
                audio: false
            });

            // Keep reference to screen track for cleanup
            this.screenTrack = this.videoStream.getVideoTracks()[0];

            // Listen for when user stops sharing via browser UI
            this.screenTrack.onended = () => {
                console.log('User ended screen sharing');
                this.stopVideo();
                // Trigger custom event for UI updates
                window.dispatchEvent(new CustomEvent('screenshare-ended'));
            };

            // Set video element source
            this.videoElement.srcObject = this.videoStream;
            this.isVideoActive = true;

            return true;
        } catch (error) {
            console.error('Error setting up screen sharing:', error);
            return false;
        }
    }

    // Start sending video frames to server
    startVideo(frameRate = 1) {
        if (!this.isVideoActive || !this.isConnected) {
            console.error('Video is not active or not connected to server');
            return false;
        }

        this.videoFrameRate = frameRate;

        // Clear existing interval if any
        if (this.videoSendInterval) {
            clearInterval(this.videoSendInterval);
        }

        // Create a canvas element for frame capture
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');

        // Set canvas size to match video
        canvas.width = this.videoElement.videoWidth || 640;
        canvas.height = this.videoElement.videoHeight || 480;

        // Start sending frames at specified rate
        this.videoSendInterval = setInterval(() => {
            if (!this.isConnected || !this.isVideoActive) {
                clearInterval(this.videoSendInterval);
                this.videoSendInterval = null;
                return;
            }

            try {
                // Draw current video frame to canvas
                context.drawImage(this.videoElement, 0, 0, canvas.width, canvas.height);

                // Convert canvas to JPEG data URL
                const dataURL = canvas.toDataURL('image/jpeg', 0.7);

                // Extract base64 data from data URL
                const base64Data = dataURL.split(',')[1];

                // Send to server with video mode metadata
                this.ws.send(JSON.stringify({
                    type: 'video',
                    data: base64Data,
                    mode: this.videoMode || 'webcam'
                }));
            } catch (error) {
                console.error('Error capturing frame:', error);
            }
        }, 1000 / this.videoFrameRate);

        return true;
    }

    // Stop sending video frames
    stopVideo() {
        if (this.videoSendInterval) {
            clearInterval(this.videoSendInterval);
            this.videoSendInterval = null;
        }
    }

    // Stop all video
    stop() {
        this.stopVideo();

        if (this.videoStream) {
            this.videoStream.getTracks().forEach(track => track.stop());
            this.videoStream = null;
        }

        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }

        this.screenTrack = null;
        this.isVideoActive = false;
        this.videoMode = null;
    }

    // Get current video mode
    getVideoMode() {
        return this.videoMode;
    }

    // Check if video is active
    isVideoStreamActive() {
        return this.isVideoActive;
    }

    // Override connect method to handle connection more carefully
    async openConnection() {
        // If already connected or connecting, don't try to connect again
        if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
            console.log('Already connected or connecting. Not creating new connection.');
            if (this.isConnected) return Promise.resolve();

            // Wait for connection to complete
            return new Promise((resolve, reject) => {
                const checkConnection = () => {
                    if (this.isConnected) {
                        resolve();
                    } else if (this.ws.readyState === WebSocket.CLOSED || this.ws.readyState === WebSocket.CLOSING) {
                        reject(new Error('WebSocket closed during connection attempt'));
                    } else {
                        setTimeout(checkConnection, 100);
                    }
                };
                checkConnection();
            });
        }

        // Actually connect if we're not already trying to
        return super.openConnection();
    }

    // Override tryReconnect to be more controlled about reconnection
    async attemptReconnect() {
        if (this.isReconnecting || this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Not reconnecting due to settings or already trying');
            return;
        }

        this.isReconnecting = true;
        this.reconnectAttempts++;

        try {
            await this.openConnection();
            console.log('Reconnected successfully');
        } catch (error) {
            console.error('Reconnection failed:', error);
        } finally {
            this.isReconnecting = false;
        }
    }

    // Override the close method to also clean up video resources
    closeConnection() {
        this.stopVideo();
        this.stop();
        super.close();
    }
}
