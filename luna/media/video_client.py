"""Async Wan2.1 I2V video generation client.

Based on v3 implementation:
- User provides simple action description (Italian)
- LLM converts to temporal prompt with timestamps
- Wan2.1 generates video from image + temporal prompt
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
import aiofiles

from luna.core.config import get_settings
from luna.ai.manager import get_llm_manager


class VideoClient:
    """Wan2.1 I2V video generation client.
    
    Flow:
    1. User input: "Luna balla lentamente" (simple Italian description)
    2. LLM generates temporal prompt with timestamps
    3. Wan2.1 generates video using image + temporal prompt
    """
    
    def __init__(self, workflow_path: Optional[Path] = None) -> None:
        """Initialize video client.
        
        Args:
            workflow_path: Path to Wan2.1 workflow JSON
        """
        self.settings = get_settings()
        self.client_id = str(uuid.uuid4())
        self.workflow_path = workflow_path or Path("comfy_workflow_video.json")
        self.llm_manager = get_llm_manager()
        
        self.timeout = aiohttp.ClientTimeout(total=600)  # 10 min for video
    
    async def generate_video(
        self,
        image_path: Path,
        user_action: str,
        character_name: str = "",
        save_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Generate video from image and user action description.
        
        Args:
            image_path: Source image for I2V
            user_action: User's action description (Italian, simple)
                         Example: "Luna balla lentamente", "she waves her hand"
            character_name: Character name for context
            save_dir: Directory to save video
            
        Returns:
            Path to generated video or None
        """
        if not self.settings.video_available:
            print("[Video] Video generation not available (requires RunPod)")
            return None
        
        comfy_url = self.settings.comfy_url
        if not comfy_url:
            print("[Video] ComfyUI URL not configured")
            return None
        
        try:
            # 1. Upload image to RunPod first!
            print(f"[Video] Uploading image to RunPod...")
            uploaded_filename = await self._upload_image(comfy_url, image_path)
            if not uploaded_filename:
                print("[Video] Failed to upload image")
                return None
            print(f"[Video] Image uploaded: {uploaded_filename}")
            
            # 2. Generate temporal prompt from user action
            print(f"[Video] Generating temporal prompt from: '{user_action}'")
            temporal_prompt = await self._build_temporal_prompt(
                user_action=user_action,
                character_name=character_name,
            )
            
            if not temporal_prompt:
                print("[Video] Failed to generate temporal prompt")
                return None
            
            print(f"[Video] Temporal prompt:\n{temporal_prompt}")
            
            # 3. Manage VRAM (unload image models)
            await self._unload_image_models(comfy_url)
            
            # 4. Load and patch workflow
            workflow = await self._load_workflow()
            self._patch_workflow(
                workflow=workflow,
                image_filename=uploaded_filename,  # Use uploaded filename only
                temporal_prompt=temporal_prompt,
                character_name=character_name,
            )
            
            # 5. Submit to Wan2.1
            print(f"[Video] Submitting to Wan2.1...")
            prompt_id = await self._submit_workflow(comfy_url, workflow)
            if not prompt_id:
                return None
            
            # 6. Wait with longer timeout (7 min DND mode)
            print("[Video] Generating... (this takes ~5-7 minutes)")
            video_path = await self._wait_and_download(
                comfy_url, prompt_id, character_name, save_dir
            )
            
            # 7. Cleanup VRAM
            await self._cleanup_vram(comfy_url)
            
            return video_path
            
        except Exception as e:
            print(f"[Video] Error: {e}")
            return None
    
    async def _upload_image(
        self,
        comfy_url: str,
        image_path: Path,
    ) -> Optional[str]:
        """Upload image to RunPod ComfyUI.
        
        Args:
            comfy_url: ComfyUI URL
            image_path: Local image path
            
        Returns:
            Uploaded filename or None
        """
        try:
            # Read image file
            async with aiofiles.open(image_path, "rb") as f:
                image_data = await f.read()
            
            filename = image_path.name
            
            async with aiohttp.ClientSession() as session:
                # Upload via ComfyUI API
                form = aiohttp.FormData()
                form.add_field("image", image_data, filename=filename, content_type="image/png")
                
                async with session.post(
                    f"{comfy_url}/upload/image",
                    data=form
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        # Return the name ComfyUI assigned
                        return data.get("name", filename)
                    else:
                        error = await resp.text()
                        print(f"[Video] Upload failed: {resp.status} - {error[:200]}")
                        # Fallback: return original filename
                        return filename
                        
        except Exception as e:
            print(f"[Video] Upload error: {e}")
            # Fallback: try with original filename
            return image_path.name
    
    async def _build_temporal_prompt(
        self,
        user_action: str,
        character_name: str = "",
    ) -> Optional[str]:
        """Convert user action to temporal prompt with timestamps.
        
        Args:
            user_action: Simple Italian description (es. "Luna balla")
            character_name: Character name
            
        Returns:
            Temporal prompt with 0s, 1s, 2s, 3s, 4s timestamps
        """
        system_prompt = """You are an expert video prompt engineer for Wan2.1 I2V (Image-to-Video).

Your task: Convert the user's simple action description into a detailed temporal prompt.

RULES:
1. Use timestamps: 0s, 1s, 2s, 3s, 4s (5 seconds total)
2. Describe ONLY physical motion - NO emotions, NO facial expressions
3. Focus on: body movement, clothing motion, hair flow, camera movement
4. Be specific about speed: slowly, gently, gradually
5. Ensure motion is smooth and continuous across timestamps

FORMAT:
0s: Initial state + beginning of motion
1s: Motion continues, describe specific movement  
2s: Peak of motion
3s: Motion slows/decays
4s: Final pose, subtle natural movement (breathing, etc)

EXAMPLE:
User: "she waves her hand"
Output:
0s: Character stands facing camera, right hand begins to raise slowly
1s: Hand continues rising to shoulder height, fingers slightly spread
2s: Hand waves gently side to side in greeting gesture
3s: Waving slows, hand begins to lower gradually
4s: Hand returns to resting position, subtle breathing motion in chest"""

        user_prompt = f"Character: {character_name or 'the character'}\nAction: {user_action}\n\nGenerate temporal prompt:"
        
        try:
            response = await self.llm_manager.generate(
                system_prompt=system_prompt,
                user_input=user_prompt,
                history=[],
                json_mode=False,
            )
            
            # Clean up response
            temporal = response.text.strip()
            
            # Ensure it has timestamps
            if "0s:" not in temporal:
                # Fallback: wrap in basic temporal structure
                temporal = f"""0s: Character begins {user_action}
1s: Motion continues naturally
2s: Peak of {user_action}
3s: Motion slows
4s: Settles into final pose"""
            
            return temporal
            
        except Exception as e:
            print(f"[Video] Temporal prompt generation failed: {e}")
            # Fallback simple temporal
            return f"""0s: Character begins {user_action}
1s: Motion continues smoothly
2s: Peak of action
3s: Motion slows gradually
4s: Settles into final pose"""
    
    async def _unload_image_models(self, comfy_url: str) -> None:
        """Unload image generation models to free VRAM.
        
        Args:
            comfy_url: ComfyUI URL
        """
        print("[Video] Unloading image models...")
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{comfy_url}/free",
                    json={"unload_models": True, "free_memory": True},
                    timeout=15,
                )
                await asyncio.sleep(3)
        except Exception as e:
            print(f"[Video] Unload warning: {e}")
    
    async def _cleanup_vram(self, comfy_url: str) -> None:
        """Cleanup VRAM after video generation.
        
        Args:
            comfy_url: ComfyUI URL
        """
        print("[Video] Cleaning up VRAM...")
        try:
            async with aiohttp.ClientSession() as session:
                # Multiple /free calls for thorough cleanup
                for i in range(5):
                    try:
                        await session.post(
                            f"{comfy_url}/free",
                            json={"unload_models": True, "free_memory": True},
                            timeout=30,
                        )
                        wait_times = [1, 2, 2, 3, 3]
                        await asyncio.sleep(wait_times[i])
                    except:
                        pass
        except Exception as e:
            print(f"[Video] Cleanup warning: {e}")
    
    async def _load_workflow(self) -> Dict[str, Any]:
        """Load Wan2.1 workflow JSON.
        
        Returns:
            Workflow dict
        """
        async with aiofiles.open(self.workflow_path, "r") as f:
            content = await f.read()
            return json.loads(content)
    
    def _patch_workflow(
        self,
        workflow: Dict[str, Any],
        image_filename: str,
        temporal_prompt: str,
        character_name: str,
    ) -> None:
        """Patch workflow with video parameters.
        
        Args:
            workflow: Workflow dict
            image_filename: Uploaded image filename (not path!)
            temporal_prompt: Temporal motion description
            character_name: Character name
        """
        # Find and patch nodes (node IDs may vary based on workflow)
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            
            inputs = node.get("inputs", {})
            class_type = node.get("class_type", "")
            
            # Load image node - use filename only (not full path)
            if class_type == "LoadImage" and "image" in inputs:
                inputs["image"] = image_filename
                print(f"[Video] Set image to: {image_filename}")
            
            # Text prompt node (temporal) - detect positive prompt node
            # Positive prompt is typically longer and contains scene description
            if class_type == "CLIPTextEncode" and "text" in inputs:
                text = str(inputs.get("text", ""))
                # Positive prompt: long, descriptive, contains video/scene words
                # Negative prompt: shorter, contains "bad", "poor", "deformed"
                is_negative = any(word in text.lower() for word in 
                    ["deformed", "bad anatomy", "poor quality", "ugly", "distorted"])
                is_positive = len(text) > 100 and not is_negative
                
                if is_positive or "0s:" in text or "motion" in text.lower():
                    inputs["text"] = temporal_prompt
                    print(f"[Video] Set temporal prompt ({len(temporal_prompt)} chars)")
            
            # Wan2.1 specific settings
            if "Wan" in class_type:
                # Resolution for Wan2.1: 512x768
                if "width" in inputs:
                    inputs["width"] = 512
                if "height" in inputs:
                    inputs["height"] = 768
                if "frames" in inputs:
                    inputs["frames"] = 81  # 81 frames = ~5 seconds
            
            # Seed
            if "seed" in inputs:
                inputs["seed"] = int(time.time()) % 1000000000
        
        # Filename prefix (VHS_VideoCombine or SaveImage/VideoSave)
        for node_id, node in workflow.items():
            class_type = node.get("class_type", "")
            if class_type.startswith("SaveImage") or \
               class_type.startswith("VideoSave") or \
               class_type == "VHS_VideoCombine":
                if "filename_prefix" in node.get("inputs", {}):
                    prefix = character_name or "video"
                    node["inputs"]["filename_prefix"] = f"{prefix}_Wan2.1"
                    print(f"[Video] Set filename prefix to: {prefix}_Wan2.1")
    
    async def _submit_workflow(
        self,
        comfy_url: str,
        workflow: Dict[str, Any],
    ) -> Optional[str]:
        """Submit workflow to ComfyUI.
        
        Args:
            comfy_url: ComfyUI URL
            workflow: Patched workflow
            
        Returns:
            Prompt ID or None
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{comfy_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id}
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    print(f"[Video] Submit failed: {resp.status} - {error[:200]}")
                    return None
                
                data = await resp.json()
                prompt_id = data.get("prompt_id")
                if prompt_id:
                    print(f"[Video] Queue ID: {prompt_id}")
                return prompt_id
    
    async def _wait_and_download(
        self,
        comfy_url: str,
        prompt_id: str,
        character: str,
        save_dir: Optional[Path],
    ) -> Optional[Path]:
        """Wait for video generation and download.
        
        Args:
            comfy_url: ComfyUI URL
            prompt_id: Prompt ID
            character: Character name
            save_dir: Save directory
            
        Returns:
            Path to video or None
        """
        # DND mode: 7 minutes wait (Wan2.1 needs time)
        max_wait = 420  # 7 minutes
        poll_interval = 10  # Check every 10 seconds
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for attempt in range(0, max_wait, poll_interval):
                await asyncio.sleep(poll_interval)
                
                progress = min(100, int((attempt / max_wait) * 100))
                print(f"[Video] Progress: {progress}% (waited {attempt}s)")
                
                try:
                    async with session.get(f"{comfy_url}/history/{prompt_id}") as r:
                        if r.status == 200:
                            data = await r.json()
                            outputs = data.get(prompt_id, {}).get("outputs", {})
                            
                            if outputs:
                                print(f"[Video] Generation complete! Outputs: {list(outputs.keys())}")
                                
                                # Download video - handle different output formats
                                for nid, node in outputs.items():
                                    print(f"[Video] Checking node {nid}: {node.keys() if isinstance(node, dict) else 'not dict'}")
                                    
                                    # Try different output formats
                                    files = []
                                    if isinstance(node, dict):
                                        files = node.get("files", []) or node.get("images", []) or node.get("gifs", [])
                                    
                                    for f in files:
                                        fname = f.get("filename", "") if isinstance(f, dict) else f
                                        print(f"[Video] Found file: {fname}")
                                        if fname.endswith((".mp4", ".webm", ".gif", ".mov")):
                                            print(f"[Video] Downloading: {fname}")
                                            return await self._download_video(
                                                session, comfy_url, fname, character, save_dir
                                            )
                                
                                print("[Video] No video file found in outputs!")
                                return None
                                
                except Exception as e:
                    print(f"[!] Poll error: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print("[Video] Timeout - generation may still be processing")
            return None
    
    async def _download_video(
        self,
        session: aiohttp.ClientSession,
        comfy_url: str,
        filename: str,
        character: str,
        save_dir: Optional[Path],
    ) -> Optional[Path]:
        """Download generated video.
        
        Args:
            session: HTTP session
            comfy_url: ComfyUI URL
            filename: Video filename
            character: Character name
            save_dir: Save directory
            
        Returns:
            Path to video or None
        """
        async with session.get(f"{comfy_url}/view?filename={filename}") as r:
            if r.status == 200:
                video_data = await r.read()
                
                if save_dir is None:
                    save_dir = Path("storage/videos")
                save_dir.mkdir(parents=True, exist_ok=True)
                
                path = save_dir / f"{character}_{int(time.time())}.mp4"
                
                async with aiofiles.open(path, "wb") as f:
                    await f.write(video_data)
                
                print(f"[Video] Saved: {path}")
                return path
            
            return None


import asyncio
