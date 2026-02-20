"""Async Stable Diffusion WebUI client for local image generation.

Uses Automatic1111 API for local image generation.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
import aiofiles

from luna.core.config import get_settings
from luna.media.builders import ImagePrompt


class SDWebUIClient:
    """Async Stable Diffusion WebUI (Automatic1111) client.
    
    Used for LOCAL mode image generation.
    """
    
    def __init__(self) -> None:
        """Initialize SD WebUI client."""
        self.settings = get_settings()
        self.timeout = aiohttp.ClientTimeout(total=120)
    
    async def generate(
        self,
        prompt: ImagePrompt,
        character_name: str = "",
        save_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Generate image using SD WebUI.
        
        Args:
            prompt: Built image prompt
            character_name: Character name
            save_dir: Directory to save image
            
        Returns:
            Path to generated image or None
        """
        sd_url = self.settings.local_sd_url
        
        try:
            # Prepare payload for SD WebUI API
            payload = {
                "prompt": prompt.positive,
                "negative_prompt": prompt.negative,
                "width": prompt.width,
                "height": prompt.height,
                "steps": prompt.steps,
                "cfg_scale": prompt.cfg_scale,
                "sampler_name": prompt.sampler,
                "seed": prompt.seed if prompt.seed else -1,
                "batch_size": 1,
                "n_iter": 1,
            }
            
            print(f"\n[SD WebUI] Generating {character_name}...")
            print(f"[SD WebUI] Size: {prompt.width}x{prompt.height}")
            print(f"[SD WebUI] Prompt: {prompt.positive[:100]}...")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Generate image
                async with session.post(
                    f"{sd_url}/sdapi/v1/txt2img",
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        print(f"[SD WebUI] Generation failed: {resp.status} - {error[:200]}")
                        return None
                    
                    data = await resp.json()
                    images = data.get("images", [])
                    
                    if not images:
                        print("[SD WebUI] No images returned")
                        return None
                    
                    # Save image
                    import base64
                    img_data = base64.b64decode(images[0])
                    
                    if save_dir is None:
                        save_dir = Path("storage/images")
                    save_dir = save_dir.resolve()  # Convert to absolute path
                    save_dir.mkdir(parents=True, exist_ok=True)
                    
                    path = save_dir / f"{character_name}_{int(time.time())}.png"
                    
                    async with aiofiles.open(path, "wb") as f:
                        await f.write(img_data)
                    
                    print(f"[SD WebUI] Saved: {path}")
                    return path.resolve()  # Return absolute path
                    
        except Exception as e:
            print(f"[SD WebUI] Error: {e}")
            return None
    
    async def check_available(self) -> bool:
        """Check if SD WebUI is running.
        
        Returns:
            True if available
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.settings.local_sd_url}/sdapi/v1/samplers") as resp:
                    return resp.status == 200
        except:
            return False
