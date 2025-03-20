from PIL import Image
from scripts.iib.parsers.model import ImageGenerationInfo, ImageGenerationParams

import re
import json
from PIL import Image
import piexif

def extract_metadata(image_path):
    try:
        img = Image.open(image_path)
        info = img.info
        if "exif" in info:
            if info.get("exif").startswith(b"Exif"):
                exif_data = piexif.load(info.get("exif"))
                raw_data = exif_data.get("Exif", {}).get(piexif.ExifIFD.UserComment)
                cleaned_data = raw_data.replace(b'\x00', b'')
                decoded_data = cleaned_data.decode('utf-8', errors='replace')
            else:
                decoded_data = info["exif"].decode('utf-8', errors='replace')
        else:
            decoded_data = info["parameters"]
        json_str = decoded_data.replace('UNICODE', '', 1)
        parsed_data = json.loads(json_str)
        if "extraMetadata" in parsed_data:
            parsed_data["extraMetadata"] = json.loads(parsed_data["extraMetadata"])
        return (parsed_data)
    except (json.decoder.JSONDecodeError, ValueError) as e:
        # JSON解析に失敗した場合の処理
        try:
            # 各行に分割
            json_list = json_str.strip().split("\n")
            
            # "Negative prompt:" の行を見つける
            negative_prompt_index = None
            for i, line in enumerate(json_list):
                if line.startswith("Negative prompt:"):
                    negative_prompt_index = i
                    break
            
            if negative_prompt_index is None:
                raise ValueError("Negative prompt: の行が見つかりません")
            
            # prompt は最初から Negative prompt: の行まで
            prompt_lines = json_list[:negative_prompt_index]
            prompt = "\n".join(prompt_lines).strip()
            
            # nprompt は Negative prompt: の行から最後の行の前まで
            nprompt_lines = json_list[negative_prompt_index:-1]
            nprompt = "\n".join(nprompt_lines).strip()
            # "Negative prompt:   " の部分を削除
            if nprompt.startswith("Negative prompt:"):
                nprompt = nprompt[len("Negative prompt:"):].strip()
            
            # model は最後の行
            model_line = json_list[-1].strip()
            model = parse_raw_text_to_dict(model_line)
            
            parsed_data = {
                "prompt": prompt,
                "negative_prompt": nprompt,
                "model": model
            }
            return parsed_data
        except Exception as inner_e:
            # さらにエラーが発生した場合は詳細なエラーメッセージを出力
            raise ValueError(f"メタデータの解析中にエラーが発生しました: {inner_e} {decoded_data}") from e


def clean_prompt(prompt_list):
    # 1. 改行を削除
    text = (prompt_list).replace("\n", " ")

    # 2. カンマで分割
    elements = [e.strip() for e in text.split(",")]

    # 3. 空要素を除去
    cleaned = [e for e in elements if e]

    return cleaned


def dict_to_string(data):
    result = []
    
    for key, value in data.items():
        if value is None or value == "": continue
        if isinstance(value, dict):
            value = ", ".join(f'"{k}: {v}"' for k, v in value.items())
        result.append(f"{key}: {value}")

    return ", ".join(result)


class Main:
    def __init__(self):
        # These two are required
        self.name = "ForgeWebUI API"
        self.source_identifier = "ForgeWebUiAPI"

    def parse(self, img: Image, file_path):
        if not self.test(img, file_path):
            raise Exception("The input image does not match the current parser.")
        info = extract_metadata(file_path)
        
        try:
            prompt = info['parameters'].pop("prompt")
            lora_pattern = r'<lora:([^:]+):([\d.]+)>'
            lora_matches = re.findall(lora_pattern, prompt)
            loras = [{"name": name, "value": float(weight)} for name, weight in lora_matches]
            meta = info["parameters"]
            negative_prompt = meta.pop("negative_prompt")
            meta.pop("seed")

            app_meta = {
            "Steps": meta["steps"],
            "Seed": info["info"]["seed"] ,
            "CFG scale": meta["cfg_scale"],
            "Sampler": info["options"]["sd_model_checkpoint"],
            "Clip skip": info["options"].get("CLIP_stop_at_last_layers", ""),
            "original_filename": info.get("original_filename", ""),
            }

            if not info:
                return ImageGenerationInfo()

            params = {
                "meta": meta,
                "pos_prompt": clean_prompt(prompt),
                "extra": {'lora': loras}
                }
            return ImageGenerationInfo(
                ", ".join(clean_prompt(prompt)) + "\nNegative prompt: " + ", ".join(clean_prompt(negative_prompt)) + "\n" + dict_to_string(app_meta) + ", " + dict_to_string(meta),
                ImageGenerationParams(
                    meta=params["meta"], pos_prompt=params["pos_prompt"], extra=params
                ),
            )
        except Exception as e:
            print(e)
            return ImageGenerationInfo()

    @classmethod
    def test(clz, img: Image, file_path: str):
        try:
            data = extract_metadata(file_path)
            assert 'parameters' in data, data
            return True
        except Exception as e:
            return False
