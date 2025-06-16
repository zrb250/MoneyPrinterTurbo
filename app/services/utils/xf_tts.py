import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import os

STATUS_FIRST_FRAME = 0
STATUS_CONTINUE_FRAME = 1
STATUS_LAST_FRAME = 2

class XfTts:
    """讯飞语音合成SDK类"""

    def __init__(self, app_id, api_key, api_secret):
        """
        初始化讯飞语音合成SDK

        参数:
            app_id: 讯飞应用ID
            api_key: 讯飞API Key
            api_secret: 讯飞API Secret
        """
        self.APPID = app_id
        self.APIKey = api_key
        self.APISecret = api_secret
        self.ws = None
        self.output_file = None
        self.text = ""
        self.error = None
        self.completed = False

        # 默认合成参数
        self.business_args = {
            "aue": "lame",  # 输出音频格式(lame表示MP3)
            "sfl": 1,       # 流式返回
            "speed": 50, #语速，可选值：[0-100]，默认为50
            "volume":50,#音量，可选值：[0-100]，默认为50
            "pitch":50, #音高，可选值：[0-100]，默认为50
            "auf": "audio/L16;rate=16000",  # 音频采样率
            "vcn": "x4_yezi",  # 发音人
            "tte": "utf8"      # 文本编码
        }

    def set_speed(self, speed):
        """设置语速"""
        self.business_args["speed"] = speed

    def set_volume(self, volume):
        """设置音量"""
        self.business_args["volume"] = volume

    def set_pitch(self, pitch):
        """设置音量"""
        self.business_args["pitch"] = pitch

    def set_voice(self, voice_name):
        """设置发音人"""
        self.business_args["vcn"] = voice_name

    def set_output_format(self, format_type):
        """设置输出格式"""
        self.business_args["aue"] = format_type

    def _create_url(self):
        """生成WebSocket连接URL"""
        url = 'wss://tts-api.xfyun.cn/v2/tts'
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接签名字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"

        # 进行hmac-sha256加密
        signature_sha = hmac.new(
            self.APISecret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        # 构建鉴权参数
        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 组合URL参数
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }

        return url + '?' + urlencode(v)

    def _on_message(self, ws, message):
        """WebSocket消息回调"""
        try:
            message = json.loads(message)
            code = message["code"]
            sid = message["sid"]
            status = message["data"]["status"]

            if status == STATUS_LAST_FRAME:
                self.completed = True
                ws.close()

            if code != 0:
                self.error = f"合成错误: {message['message']} (code: {code}, sid: {sid})"
                ws.close()
            else:
                audio = message["data"]["audio"]
                audio = base64.b64decode(audio)
                if self.output_file:
                    with open(self.output_file, 'ab') as f:
                        f.write(audio)
        except Exception as e:
            self.error = f"消息处理异常: {str(e)}"
            ws.close()

    def _on_error(self, ws, error):
        """WebSocket错误回调"""
        self.error = f"WebSocket错误: {str(error)}"

    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket关闭回调"""
        if self.output_file and os.path.exists(self.output_file) and os.path.getsize(self.output_file) == 0:
            os.remove(self.output_file)

        return None

    def _on_open(self, ws):
        """WebSocket连接建立回调"""
        def run(*args):
            d = {
                "common": {"app_id": self.APPID},
                "business": self.business_args,
                "data": {
                    "status": STATUS_LAST_FRAME,
                    "text": str(base64.b64encode(self.text.encode('utf-8')), "UTF8")
                }
            }
            ws.send(json.dumps(d))
            # 清空输出文件（如果已存在）
            if self.output_file and os.path.exists(self.output_file):
                os.remove(self.output_file)

        thread.start_new_thread(run, ())

    def synthesize(self, text, output_file):
        """
        执行语音合成

        参数:
            text: 要合成的文本
            output_file: 输出文件路径

        返回:
            bool: 合成是否成功
        """
        self.text = text
        self.output_file = output_file
        self.error = None
        self.completed = False

        try:
            websocket.enableTrace(False)
            ws_url = self._create_url()
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=lambda ws, msg: self._on_message(ws, msg),
                on_error=lambda ws, error: self._on_error(ws, error),
                on_close=lambda ws, *args: self._on_close(ws, *args)
            )
            self.ws.on_open = lambda ws: self._on_open(ws)
            self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

            return self.completed and not self.error
        except Exception as e:
            self.error = f"合成异常: {str(e)}"
            return False

    def get_error(self):
        """获取错误信息（如果合成失败）"""
        return self.error


if __name__ == "__main__":
    # 创建TTS实例
    tts = xf_tts(
        app_id='4a0b1ca3',
        api_key='d1edda7edeb51e1fe0e8382c20a9aa61',
        api_secret='MzU0YTNlYTgzZmFhNTQ5MjgwZmFiN2U4'
    )

    # 可选：设置发音人（默认为x4_yezi）
    # tts.set_voice("xiaoyan")  # 更换为小燕发音人

    # 执行语音合成
    text = "学习不仅仅是为了获取知识，它更是一种探索未知、理解世界的方式。"
    result = tts.synthesize(text, "output.mp3")

    if result:
        print("语音合成成功！输出文件: output.mp3")
    else:
        print(f"语音合成失败: {tts.get_error()}")