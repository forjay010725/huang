import serial
import serial.tools.list_ports
import time
import re
import threading
import sys
import json
import os


class RobustSerial:
    """增强型串口管理类"""

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
        """发送AT指令"""
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
                        if self.ser.in_waiting:
                            response += self.ser.read(self.ser.in_waiting).decode(errors="ignore")
                            if "\n" in response:  # 检测完整响应
                                break
                        time.sleep(0.1)

                    response = response.strip()
                    print(f"[RX←{self.port}] {response}")

                    # 检查预期响应
                    if expected_response and expected_response not in response:
                        print(f"⚠️ 未收到预期响应，重试中 ({attempt + 1}/{retries})")
                        continue

                    return response

                except serial.SerialException as e:
                    print(f"⚠️ 通信错误: {str(e)}")
                    if "reset" in str(e).lower():
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


class HostController:
    """主机端控制器"""

    CONFIG_FILE = "host_config.json"

    def __init__(self):
        self.ser = None
        self.target_mac = None
        self.config = self.load_config()

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"port": "", "target_mac": ""}

    def save_config(self):
        """保存配置文件"""
        with open(self.CONFIG_FILE, "w") as f:
            json.dump({
                "port": self.ser.port if self.ser else "",
                "target_mac": self.target_mac
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

        prompt = "\n请选择主机设备序号"
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
        """恢复出厂设置"""
        print("⚙️ 恢复出厂设置...")
        response = self.ser.send_at_command("AT+RESTORE", expected_response="+OK", wait_after=2)
        return "+OK" in response

    def set_role(self, role=1):
        """设置设备角色为主机"""
        print("⚙️ 设置设备为主机角色...")
        response = self.ser.send_at_command(f"AT+ROLE={role}", expected_response="+OK")
        self.ser.send_at_command("AT+RESET")
        return "+OK" in response

    def scan_devices(self):
        """扫描BLE设备"""
        print("🔍 开始扫描BLE设备...")
        response = self.ser.send_at_command("AT+SCAN=1,5,1")  # 扫描5秒

        if "+OK" not in response:
            return []

        # 收集扫描结果
        scan_data = ""
        start_time = time.time()
        while time.time() - start_time < 6:  # 等待扫描完成
            if self.ser.ser.in_waiting:
                data = self.ser.ser.read(self.ser.ser.in_waiting).decode(errors="ignore")
                scan_data += data
                print(data.strip())
            time.sleep(0.1)

        # 提取MAC地址
        mac_pattern = r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})"
        return re.findall(mac_pattern, scan_data)

    def select_target_device(self, devices):
        """选择目标设备"""
        print("\n🔍 扫描到的设备:")
        for i, mac in enumerate(devices, 1):
            print(f"{i}. {mac}")

        # 使用配置中的默认MAC
        default_index = None
        if self.config.get("target_mac"):
            for i, mac in enumerate(devices):
                if mac == self.config["target_mac"]:
                    default_index = i + 1
                    break

        prompt = "\n请选择要连接的设备序号"
        if default_index:
            prompt += f" (默认: {default_index})"
        prompt += ": "

        try:
            selection = input(prompt).strip()
            if not selection and default_index:
                selection = str(default_index)

            index = int(selection)
            if 1 <= index <= len(devices):
                return devices[index - 1]
            print("❌ 选择超出范围")
        except ValueError:
            print("❌ 请输入有效数字")
        return None

    def connect_to_device(self, target_mac):
        """连接目标设备"""
        print(f"🔗 尝试连接设备 {target_mac}...")

        # 停止扫描
        self.ser.send_at_command("AT+SCAN=0")
        time.sleep(1)

        # 发送连接命令
        response = self.ser.send_at_command(
            f"AT+CONNECT=,{target_mac}",
            expected_response="+OK",
            wait_after=1
        )

        if "+OK" not in response:
            return False

        # 等待连接确认
        print("⏳ 等待连接确认...")
        start_time = time.time()
        while time.time() - start_time < 15:
            if self.ser.ser.in_waiting:
                data = self.ser.ser.read(self.ser.ser.in_waiting).decode()
                print(data.strip())
                if "CONNECTED" in data:
                    return True
                elif "DISCONNECT" in data or "ERROR" in data:
                    return False
            time.sleep(0.5)
        return False

    def enable_transparent_mode(self):
        """启用透传模式"""
        print("⚡ 启用透传模式...")
        response = self.ser.send_at_command("AT+TRM_HANDLE=1", expected_response="+OK")
        return "+OK" in response

    def run(self):
        """主机端主程序"""
        print("=" * 60)
        print("BLE主机端配置工具 v1.6")
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
            print(f"\n📋 主机设备信息:")
            print(f"MAC地址: {mac}")

        # 恢复出厂设置
        if not self.factory_reset():
            print("❌ 恢复出厂设置失败")
            input("按任意键退出...")
            return

        # 设置为主机角色
        if not self.set_role():
            print("❌ 设置主机角色失败")
            input("按任意键退出...")
            return

        # 扫描设备
        devices = self.scan_devices()
        if not devices:
            print("❌ 未扫描到任何设备")
            input("按任意键退出...")
            return

        # 选择目标设备
        target_mac = self.select_target_device(devices)
        if not target_mac:
            print("❌ 未选择目标设备")
            input("按任意键退出...")
            return

        self.target_mac = target_mac

        # 连接设备
        if not self.connect_to_device(target_mac):
            print("❌ 连接失败")
            input("按任意键退出...")
            return

        # 启用透传模式
        if not self.enable_transparent_mode():
            print("⚠️ 透传模式启用失败")
        else:
            print("✅ 已进入透传模式")

        # 保存配置
        self.save_config()

        print("\n操作完成，按任意键退出...")
        input()


if __name__ == "__main__":
    controller = HostController()
    controller.run()