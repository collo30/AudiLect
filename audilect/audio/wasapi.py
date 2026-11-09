import sys
import sounddevice as sd
from typing import List, Dict, Optional, Any


def list_audio_devices() -> List[Dict[str, Any]]:
    """List available audio devices and detect WASAPI loopback devices."""
    devices = sd.query_devices()
    device_list = []
    for idx, d in enumerate(devices):
        hostapi = sd.query_hostapis(d['hostapi'])
        is_wasapi = "WASAPI" in hostapi.get('name', '').upper()
        device_list.append({
            "id": idx,
            "name": d['name'],
            "hostapi": hostapi.get('name', ''),
            "max_input_channels": d['max_input_channels'],
            "max_output_channels": d['max_output_channels'],
            "default_samplerate": d['default_samplerate'],
            "is_wasapi": is_wasapi
        })
    return device_list


def get_default_wasapi_loopback_device() -> Optional[int]:
    """
    Finds the default WASAPI output device for loopback capture.
    On Windows WASAPI, looping back an output device requires opening it with loopback=True.
    """
    try:
        devices = sd.query_devices()
        wasapi_api_idx = None
        for i, api in enumerate(sd.query_hostapis()):
            if "WASAPI" in api['name'].upper():
                wasapi_api_idx = i
                break

        if wasapi_api_idx is None:
            return None

        # Return the default output device under WASAPI
        default_out = sd.query_hostapis(wasapi_api_idx).get('default_output')
        return default_out
    except Exception:
        return None
