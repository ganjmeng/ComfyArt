import comfy.ops
import comfy.sd
import folder_paths

from . import timeline


class PreciseUNETLoader:
    DESCRIPTION = "Loads a diffusion model with manual cast ops, skipping the --fast fp8_matrix_mult path that breaks unscaled fp8 checkpoints such as Qwen Image 2512."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"unet_name": (folder_paths.get_filename_list("diffusion_models"),)}}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "load"
    CATEGORY = "ComfyArt"

    def load(self, unet_name):
        path = folder_paths.get_full_path_or_raise("diffusion_models", unet_name)
        return (comfy.sd.load_diffusion_model(path, model_options={"custom_operations": comfy.ops.manual_cast}),)


NODE_CLASS_MAPPINGS = {"ComfyArtPreciseUNETLoader": PreciseUNETLoader, **timeline.NODE_CLASS_MAPPINGS}
NODE_DISPLAY_NAME_MAPPINGS = {"ComfyArtPreciseUNETLoader": "ComfyArt Precise UNET Loader", **timeline.NODE_DISPLAY_NAME_MAPPINGS}
