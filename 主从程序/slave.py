import serial
import serial.tools.list_ports
import time
import re
import threading
import sys
import json
import os


class RobustSerial:
    """增强型串口管理类 - 修复设备未配置错误"""

    def __init__(self, port, baudrate=115200, timeout=20):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.lock = threading.Lock()
        self.connect()

    def connect(self):
        """建立串口连接"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()

            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"✅ 串口连接成功: {self.port}")
            return True
        except serial.SerialException as e:
            print(f"❌ 串口连接失败: {self.port} - {str(e)}")
            return False

    def send_at_command(self, command, expected_response=None, retries=3, wait_after=0):
        """发送AT指令 - 增强错误处理"""
        with self.lock:
            for attempt in range(retries):
                try:
                    # 检查连接状态
                    if not self.ser or not self.ser.is_open:
                        print("⚠️ 串口未连接，尝试重新连接...")
                        if not self.connect():
                            continue

                    # 清除缓冲区
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()

                    # 发送命令
                    self.ser.write((command + "\r\n").encode())
                    print(f"[TX→{self.port}] {command}")

                    # 读取响应
                    response = ""
                    start_time = time.time()
                    while time.time() - start_time < self.timeout:
                        try:
                            if self.ser.in_waiting:
                                data = self.ser.read(self.ser.in_waiting)
                                response += data.decode(errors="ignore")
                                if "\n" in response:  # 检测完整响应
                                    break
                        except serial.SerialException as e:
                            if "device not configured" in str(e).lower():
                                print("⚠️ 设备未配置，尝试重新连接...")
                                self.connect()
                                continue
                            else:
                                raise e
                        time.sleep(0.1)

                    response = response.strip()
                    print(f"[RX←{self.port}] {response}")

                    # 重启命令特殊处理
                    if "AT+RESET" in command or "AT+RESTORE" in command:
                        print("🔄 设备重启中，关闭当前连接...")
                        try:
                            self.ser.close()
                        except:
                            pass
                        print("⏳ 等待设备重启完成...")
                        time.sleep(3)  # 延长等待时间
                        self.connect()  # 重新连接
                        time.sleep(wait_after)  # 额外等待时间

                    # 检查预期响应
                    if expected_response and expected_response not in response:
                        print(f"⚠️ 未收到预期响应，重试中 ({attempt + 1}/{retries})")
                        continue

                    return response

                except serial.SerialException as e:
                    print(f"⚠️ 通信错误: {str(e)}")
                    if "reset" in str(e).lower() or "device not configured" in str(e).lower():
                        self.connect()  # 尝试重新连接
                    time.sleep(0.5)
            return ""

    def close(self):
        """安全关闭串口"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                print(f"🔌 已关闭串口: {self.port}")
            except:
                pass


class SlaveController:
    """从机端控制器 - 修复版本"""

    CONFIG_FILE = "slave_config.json"

    def __init__(self):
        self.ser = None
        self.config = self.load_config()

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"port": ""}

    def save_config(self):
        """保存配置文件"""
        if self.ser:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({
                    "port": self.ser.port
                }, f)

    def select_serial_port(self):
        """用户选择串口设备"""
        ports = serial.tools.list_ports.comports()
        if not ports:
            print("❌ 未检测到可用串口")
            return None

        print("\n🔍 可用串口设备:")
        for i, port in enumerate(ports, 1):
            print(f"{i}. {port.device} - {port.description}")

        # 使用配置中的默认端口
        default_index = None
        if self.config.get("port"):
            for i, port in enumerate(ports):
                if port.device == self.config["port"]:
                    default_index = i + 1
                    break

        prompt = "\n请选择从机设备序号"
        if default_index:
            prompt += f" (默认: {default_index})"
        prompt += ": "

        try:
            selection = input(prompt).strip()
            if not selection and default_index:
                selection = str(default_index)

            index = int(selection)
            if 1 <= index <= len(ports):
                return ports[index - 1].device
            print("❌ 选择超出范围")
        except ValueError:
            print("❌ 请输入有效数字")
        return None

    def get_mac_address(self):
        """获取设备MAC地址"""
        if not self.ser:
            return None

        response = self.ser.send_at_command("AT+MAC?", expected_response="MAC=")
        if "MAC=" in response:
            return response.split("=")[1].strip()
        return None

    def factory_reset(self):
        """恢复出厂设置 - 增加等待时间"""
        print("⚙️ 恢复出厂设置...")
        response = self.ser.send_at_command("AT+RESTORE", expected_response="+OK", wait_after=3)
        return "+OK" in response

    def set_role(self, role=0):
        """设置设备角色为从机 - 增加错误处理"""
        print("⚙️ 设置设备为从机角色...")
        response = self.ser.send_at_command(f"AT+ROLE={role}", expected_response="+OK")

        # 重启设备前增加额外等待
        time.sleep(1)
        self.ser.send_at_command("AT+RESET", wait_after=2)
        return "+OK" in response

    def enable_broadcast(self):
        """启用广播 - 简化实现"""
        print("📻 启用广播...")
        response = self.ser.send_at_command("AT+ADV=1,1,200", expected_response="+OK")
        return "+OK" in response

    def enable_auto_connect(self):
        """启用自动连接 - 简化实现"""
        print("⚙️ 配置自动连接...")
        # 设置设备上电自动进入广播模式
        response = self.ser.send_at_command("AT+ADVSTART=1", expected_response="+OK")
        return "+OK" in response

    def enable_transparent_mode(self):
        """启用透传模式 - 简化实现"""
        print("⚡ 启用透传模式...")
        response = self.ser.send_at_command("AT+TRM_HANDLE=1", expected_response="+OK")
        return "+OK" in response

    def run(self):
        """从机端主程序"""
        print("=" * 60)
        print("BLE从机端配置工具 v1.6")
        print("=" * 60)

        # 选择串口
        port = self.select_serial_port()
        if not port:
            input("按任意键退出...")
            return

        # 初始化串口
        self.ser = RobustSerial(port)

        # 获取设备信息
        mac = self.get_mac_address()
        if mac:
            print(f"\n📋 从机设备信息:")
            print(f"MAC地址: {mac}")
            print("请将此MAC地址提供给主机端")

        # 恢复出厂设置 - 增加额外等待
        print("⏳ 正在恢复出厂设置，请稍候...")
        if not self.factory_reset():
            print("❌ 恢复出厂设置失败")
            input("按任意键退出...")
            return
        time.sleep(2)  # 额外等待

        # 设置为从机角色 - 增加额外等待
        print("⏳ 正在设置从机角色，请稍候...")
        if not self.set_role():
            print("❌ 设置从机角色失败")
            input("按任意键退出...")
            return
        time.sleep(2)  # 额外等待

        # 启用广播
        print("⏳ 正在启用广播，请稍候...")
        if not self.enable_broadcast():
            print("❌ 启用广播失败")
            input("按任意键退出...")
            return

        # 配置自动连接
        print("⏳ 正在配置自动连接，请稍候...")
        if not self.enable_auto_connect():
            print("⚠️ 自动连接配置失败")

        # 启用透传模式
        print("⏳ 正在启用透传模式，请稍候...")
        if not self.enable_transparent_mode():
            print("⚠️ 透传模式启用失败")
        else:
            print("✅ 已配置为自动进入透传模式")

        # 保存配置
        self.save_config()

        print("\n配置完成，设备已准备就绪")
        print("1. 设备上电后将自动广播并等待连接")
        print("2. 主机连接后将自动进入透传模式")
        print("\n按任意键退出...")
        input()


if __name__ == "__main__":
    controller = SlaveController()
    controller.run()