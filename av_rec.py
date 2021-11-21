from __future__ import print_function, division
import numpy as np
import cv2
import pyaudio
import wave
import threading
import time
import subprocess
import os
from pydub import AudioSegment
import argparse

class VideoRecorder():
    def __init__(self, filenname="temp_video.avi", camindex=1):
        self.open = True
        self.device_index = camindex
        self.video_filename = filenname
        self.video_cap = cv2.VideoCapture(self.device_index)
        width = int(self.video_cap.get(3))
        height = int(self.video_cap.get(4))
        self.fps = int(self.video_cap.get(5))  # fps should be the minimum constant rate at which the camera can
        self.frameSize = (width, height)  # video formats and sizes also depend and vary according to the camera used
        self.video_writer = cv2.VideoWriter_fourcc(*'X264')
        self.video_out = cv2.VideoWriter(self.video_filename, self.video_writer, self.fps, self.frameSize)
        self.frame_counts = 1
        self.start_time = time.time()

    def record(self):
        while self.open:
            ret, video_frame = self.video_cap.read()
            if ret:
                self.video_out.write(video_frame)
                self.frame_counts += 1
                cv2.imshow('video_frame', video_frame)
                cv2.waitKey(1)
            else:
                break

    def stop(self):
        if self.open:
            self.open = False
            self.video_out.release()
            self.video_cap.release()
            cv2.destroyAllWindows()

    def start(self):
        video_thread = threading.Thread(target=self.record)
        video_thread.start()

class AudioRecorder():
    def __init__(self, filename="temp_audio.wav", rate=48000, fpb=2**12, channels=7, audio_index=8):
        self.open = True
        self.rate = rate
        self.frames_per_buffer = fpb
        self.channels = channels
        self.format = pyaudio.paInt32
        self.input_sample_width = 4
        self.audio_filename = filename
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=self.format,
                                      channels=self.channels,
                                      rate=self.rate,
                                      input=True,
                                      input_device_index=audio_index,
                                      frames_per_buffer=self.frames_per_buffer,
                                      )

    def record(self):
        self.stream.start_stream()
        with wave.open(self.audio_filename , "wb") as outfile:
            outfile.setnchannels(1)  # We want to write only first channel from each frame
            outfile.setsampwidth(self.input_sample_width)
            outfile.setframerate(self.rate)

            while self.open:
                available_frames = self.stream.get_read_available()
                data = self.stream.read(available_frames)
                first_channel_data = np.frombuffer(data, dtype=np.int32)[0::7].tobytes()
                outfile.writeframesraw(first_channel_data)

        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()

    def stop(self):
        if self.open:
            self.open = False

    def start(self):
        audio_thread = threading.Thread(target=self.record)
        audio_thread.start()

def start_AVrecording(filename="test", camindex=1, audio_index=8, channels=7, sample_rate=48000):
    global video_thread
    global audio_thread
    audio_thread = AudioRecorder(filename="temp_audio.wav", rate=sample_rate, fpb=2 ** 12, channels=channels,
                                 audio_index=audio_index)
    video_thread = VideoRecorder(filenname="temp_video.avi", camindex=camindex)
    video_thread.start()
    audio_thread.start()
    return filename

def match_target_amplitude(sound, target_dBFS):
    change_in_dBFS = target_dBFS - sound.dBFS
    return sound.apply_gain(change_in_dBFS)

def stop_AVrecording(filename="test"):
    audio_thread.stop()

    frame_counts = video_thread.frame_counts
    elapsed_time = time.time() - video_thread.start_time
    recorded_fps = frame_counts / elapsed_time
    print("total frames " + str(frame_counts))
    print("elapsed time " + str(elapsed_time))
    print("recorded fps " + str(recorded_fps))
    video_thread.stop()

    # Makes sure the threads have finished
    while threading.active_count() > 1:
        time.sleep(1)

    sound = AudioSegment.from_file("temp_audio.wav", "wav")
    normalized_sound = match_target_amplitude(sound, -35.0)
    normalized_sound.export("temp_audio.wav", format="wav")
    # Merging audio and video signal
    print("Normal recording\nMuxing")
    cmd = "ffmpeg -r " + str(recorded_fps) + " -y -i temp_video.avi -c:v libx264 -crf 18 -r 30 -preset slow -c:a copy temp_video2.avi"
    subprocess.call(cmd, shell=True)
    cmd = "ffmpeg -r " + str(
        recorded_fps) + " -y -ac 2 -channel_layout mono -i temp_audio.wav  -i temp_video2.avi -c:v libx264 -crf 18 -r 30 -preset slow -c:a copy " + filename + ".avi"
    subprocess.call(cmd, shell=True)
    print("..")

def file_manager(filename="test"):
    "Required and wanted processing of final files"
    local_path = os.getcwd()
    if os.path.exists(str(local_path) + "/temp_audio.wav"):
        os.remove(str(local_path) + "/temp_audio.wav")
    if os.path.exists(str(local_path) + "/temp_video.avi"):
        os.remove(str(local_path) + "/temp_video.avi")
    if os.path.exists(str(local_path) + "/temp_video2.avi"):
        os.remove(str(local_path) + "/temp_video2.avi")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="video")
    parser.add_argument("--num_seconds", default='15', type=int)
    args = parser.parse_args()

    start_AVrecording(filename="test", camindex=1, audio_index=8, channels=7, sample_rate=48000)
    time.sleep(args.num_seconds)
    stop_AVrecording()
    file_manager()