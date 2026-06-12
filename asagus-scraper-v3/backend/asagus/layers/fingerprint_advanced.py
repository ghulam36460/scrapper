"""Advanced browser fingerprinting for detection research."""

from __future__ import annotations

import hashlib


class AdvancedFingerprinting:
    """
    Collect comprehensive browser fingerprinting signals.
    References:
    - FingerprintJS: https://github.com/fingerprintjs/fingerprintjs
    - CreepJS: https://github.com/abrahamjuliot/creepjs
    """

    async def collect_fingerprint_signals(self, page) -> dict[str, object]:
        """Collect comprehensive fingerprint signals from browser context."""
        canvas_fp = await self._canvas_fingerprint(page)
        webgl_fp = await self._webgl_fingerprint(page)
        audio_fp = await self._audio_fingerprint(page)
        fonts = await self._detect_fonts(page)
        hardware = await self._detect_hardware(page)
        webrtc = await self._detect_webrtc(page)
        plugins = await self._detect_plugins(page)

        combined_fingerprint = {
            "canvas": canvas_fp,
            "webgl": webgl_fp,
            "audio": audio_fp,
            "fonts": fonts,
            "hardware": hardware,
            "webrtc": webrtc,
            "plugins": plugins,
            "entropy_score": self._calculate_entropy(
                canvas_fp, webgl_fp, audio_fp, fonts, hardware
            ),
        }

        return combined_fingerprint

    async def _canvas_fingerprint(self, page) -> dict[str, object]:
        """Canvas fingerprinting via rendering."""
        canvas_script = """
        () => {
            try {
                const canvas = document.createElement('canvas');
                canvas.width = 280;
                canvas.height = 60;
                const ctx = canvas.getContext('2d');
                ctx.textBaseline = 'top';
                ctx.font = '14px Arial';
                ctx.textBaseline = 'alphabetic';
                ctx.fillStyle = '#f60';
                ctx.fillRect(125, 1, 62, 20);
                ctx.fillStyle = '#069';
                ctx.fillText('Fingerprint', 2, 15);
                ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
                ctx.fillText('Fingerprint', 4, 17);
                const dataUrl = canvas.toDataURL();
                return {
                    hash: dataUrl.substring(0, 100),
                    supports: 'canvas' in document.createElement('canvas'),
                };
            } catch(e) {
                return { error: e.message };
            }
        }
        """
        return await page.evaluate(canvas_script)

    async def _webgl_fingerprint(self, page) -> dict[str, object]:
        """WebGL fingerprinting."""
        webgl_script = """
        () => {
            try {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl') || 
                           canvas.getContext('experimental-webgl');
                if (!gl) return { error: 'WebGL not supported' };
                
                const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                return {
                    vendor: gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL),
                    renderer: gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL),
                    supported_extensions: gl.getSupportedExtensions().length,
                };
            } catch(e) {
                return { error: e.message };
            }
        }
        """
        return await page.evaluate(webgl_script)

    async def _audio_fingerprint(self, page) -> dict[str, object]:
        """AudioContext fingerprinting."""
        audio_script = """
        () => {
            try {
                const AudioContext = window.AudioContext || 
                                    window.webkitAudioContext;
                if (!AudioContext) return { error: 'AudioContext not supported' };
                
                const context = new AudioContext();
                return {
                    sample_rate: context.sampleRate,
                    state: context.state,
                    max_channel_count: context.destination.maxChannelCount,
                    supported: true,
                };
            } catch(e) {
                return { error: e.message };
            }
        }
        """
        return await page.evaluate(audio_script)

    async def _detect_fonts(self, page) -> list[str]:
        """Detect available fonts."""
        fonts_script = """
        () => {
            const testFonts = [
                'Arial', 'Courier', 'Georgia', 'Helvetica', 'Palantino',
                'Times New Roman', 'Verdana', 'Comic Sans MS', 'Trebuchet MS',
                'Segoe UI', 'Tahoma', 'Microsoft Sans Serif', 'DejaVu Sans',
                'Bitstream Vera Sans', 'Ubuntu Font Family',
            ];
            
            const measurer = document.createElement('span');
            measurer.style.visibility = 'hidden';
            document.body.appendChild(measurer);
            
            const detected = [];
            for (const font of testFonts) {
                measurer.style.fontFamily = `"${font}", sans-serif`;
                const width1 = measurer.offsetWidth;
                
                measurer.style.fontFamily = 'sans-serif';
                const width2 = measurer.offsetWidth;
                
                if (width1 !== width2) {
                    detected.push(font);
                }
            }
            
            document.body.removeChild(measurer);
            return detected;
        }
        """
        try:
            return await page.evaluate(fonts_script)
        except Exception:
            return []

    async def _detect_hardware(self, page) -> dict[str, object]:
        """Detect hardware capabilities."""
        hardware_script = """
        () => {
            return {
                cpu_cores: navigator.hardwareConcurrency || 'unknown',
                device_memory: navigator.deviceMemory || 'unknown',
                max_touch_points: navigator.maxTouchPoints || 0,
                platform: navigator.platform,
                language: navigator.language,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                screen_width: window.screen.width,
                screen_height: window.screen.height,
                color_depth: window.screen.colorDepth,
            };
        }
        """
        return await page.evaluate(hardware_script)

    async def _detect_webrtc(self, page) -> dict[str, object]:
        """Detect WebRTC."""
        webrtc_script = """
        () => {
            return {
                webrtc_available: !!(window.RTCPeerConnection || 
                                      window.webkitRTCPeerConnection ||
                                      window.mozRTCPeerConnection),
                media_devices_available: !!navigator.mediaDevices,
            };
        }
        """
        return await page.evaluate(webrtc_script)

    async def _detect_plugins(self, page) -> dict[str, object]:
        """Detect browser plugins."""
        plugins_script = """
        () => {
            const plugins = [];
            for (let plugin of navigator.plugins) {
                plugins.push({ name: plugin.name });
            }
            return { plugin_count: plugins.length };
        }
        """
        try:
            return await page.evaluate(plugins_script)
        except Exception:
            return {"plugin_count": 0}

    def _calculate_entropy(self, *fingerprints) -> float:
        """Rough entropy calculation for fingerprint uniqueness."""
        combined = str(fingerprints)
        entropy_score = len(set(combined)) / len(combined) if combined else 0
        return round(entropy_score, 2)

    def state(self) -> dict[str, object]:
        return {
            "purpose": "Collect advanced fingerprinting signals for research analysis",
            "signals_collected": [
                "canvas_hash",
                "webgl_vendor_renderer",
                "audio_context_properties",
                "installed_fonts",
                "hardware_capabilities",
                "webrtc_availability",
                "browser_plugins",
                "timezone_locale",
                "screen_resolution",
            ],
            "entropy_analysis": True,
            "use_case": "Benchmark anti-bot detection mechanisms",
        }
