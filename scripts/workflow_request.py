"""Read structured Actions inputs without interpolating user text into shell code."""
import json
import os
from pathlib import Path
from shorts_pipeline.config import request_config

data = json.loads(os.environ['SHORTS_INPUTS'])
window=json.loads('['+data['source_window']+']') if data.get('source_window','').strip() else None
request = request_config({'title':data['title'], 'source':data['source_url'],
                          'brief':data['brief'], 'story_notes':data.get('story_notes',''),
                          'narrator':data['narrator'], 'target_seconds':float(data['target_seconds']),
                          'aspect':data['aspect'], 'tts_model':data['speech_model'],
                          'script_model':data.get('writer_model','qwen3:4b-instruct-2507-q4_K_M'),'source_window':window})
Path('work').mkdir(exist_ok=True)
Path('work/request.json').write_text(json.dumps(request,indent=2),encoding='utf-8')
