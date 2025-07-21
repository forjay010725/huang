import serial
import serial.tools.list_ports
import time
import re
import threading
import sys


class RobustSerial:
    """增强型串口管理类，处理设备重启后的断连问题"""

    def __init__(self, port, baudrate=115200, timeout=20):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.original_port = port  # 保存原始端口信息
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
        """发送AT指令（自动处理重启断连）"""
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

                    # 重启命令特殊处理
                    if "AT+RESET" in command or "AT+RESTORE" in command:
                        print("🔄 设备重启中，关闭当前连接...")
                        self.ser.close()
                        print("⏳ 等待设备重启完成...")
                        time.sleep(1)  # 根据手册要求等待3秒
                        self.connect()  # 重新连接
                        time.sleep(wait_after)  # 额外等待时间

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


class BlePairer:
    """BLE设备配对器（兼容EWM104-BT57U）"""
    ERROR_CODES = {
        1: "指令不存在",
        2: "参数错误",
        3: "操作失败/超时",
        4: "当前角色不支持该指令"
    }

    def __init__(self, port1=None, port2=None):
        self.ser1 = RobustSerial(port1) if port1 else None
        self.ser2 = RobustSerial(port2) if port2 else None
        self.mac_cache = {}

    def get_mac_address(self, ser):
        """获取设备MAC地址（带缓存）"""
        if not ser:
            return None

        if ser.port in self.mac_cache:
            return self.mac_cache[ser.port]

        response = ser.send_at_command("AT+MAC?", expected_response="MAC=")
        if "MAC=" in response:
            mac = response.split("=")[1].strip()
            self.mac_cache[ser.port] = mac
            return mac
        return None

    def factory_reset(self, ser):
        """恢复出厂设置（处理重启断连）"""
        print("⚙️ 恢复出厂设置...")
        response = ser.send_at_command("AT+RESTORE", expected_response="+OK", wait_after=2)
        return "+OK" in response

    def set_role(self, ser, role):
        """设置设备角色（主/从）"""
        role_name = {0: "从机", 1: "主机", 2: "主从一体", 3: "Beacon"}.get(role, "未知")
        print(f"⚙️ 设置设备为{role_name}角色...")
        response = ser.send_at_command(f"AT+ROLE={role}", expected_response="+OK")
        ser.send_at_command("AT+RESET")
        return "+OK" in response

    def enable_broadcast(self, ser):
        """启用从机广播（可连接模式）"""
        print("📻 启用从机广播...")
        response = ser.send_at_command("AT+ADV=1,1,200", expected_response="+OK")
        return "+OK" in response

    # def set_tx_power(self, ser, power=4):
    #     """设置发射功率（0-4dBm）"""
    #     print(f"📶 设置发射功率为 {power}dBm...")
    #     response = ser.send_at_command(f"AT+PWR={power}", expected_response="+OK")
    #     return "+OK" in response

    def scan_devices(self, host_ser):
        """主机扫描从机设备"""
        print("🔍 开始扫描BLE设备...")
        response = host_ser.send_at_command("AT+SCAN=0,1,1")

        print(str(response))
        if "+OK" not in response:
            return []
        #time.sleep(1)
        # 收集扫描结果
        # scan_data = ""
        # start_time = time.time()
        # while time.time() - start_time < 12:
        #     if host_ser.ser.in_waiting:
        #         scan_data += host_ser.ser.read(host_ser.ser.in_waiting).decode(errors="ignore")
        #     time.sleep(0.1)
        #
        # #print(f"📡 扫描结果:\n{scan_data}")
        #
        # # 提取MAC地址
        # mac_pattern = r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})"
        # return re.findall(mac_pattern, scan_data)

    def connect_to_device(self, host_ser, target_mac):
        # 停止扫描
        #host_ser.send_at_command("AT+SCAN=0")
        #time.sleep(2)

        # 发送连接命令
        response = host_ser.send_at_command(
            f"AT+CONNECT=,{target_mac}",
            expected_response="+OK",
            wait_after=1
        )

        # 专用连接状态监听
        return self._wait_for_connection_status(host_ser)

    def _wait_for_connection_status(self, ser):
        """专用方法监听连接状态"""
        timeout = 20  # 延长至20秒
        start_time = time.time()

        while time.time() - start_time < timeout:
            if ser.ser.in_waiting:
                data = ser.ser.read(ser.ser.in_waiting).decode()
                print(data.strip())
                if "CONNECTED" in data:
                    return True
                elif "DISCONNECT" in data:
                    return False
            time.sleep(0.5)
        return True


    def enable_transparent_mode(self, ser):
        """启用透传模式"""
        print("⚡ 启用透传模式...")
        haneld = ser.send_at_command("AT+CONNECT_LIST?")
        print(haneld)
        response = ser.send_at_command("AT+TRM_HANDLE=1")
        return "+OK" in response


    def auto_pair(self):
        """完整的自动配对流程"""
        if not self.ser1 or not self.ser2:
            print("❌ 串口未正确初始化")
            return False

        try:
            # ===== 1. 获取设备信息 =====
            mac1 = self.get_mac_address(self.ser1)
            mac2 = self.get_mac_address(self.ser2)
            if not mac1 or not mac2:
                print("❌ 获取MAC地址失败")
                return False

            print("\n📋 设备信息:")
            print(f"设备1 ({self.ser1.port}): {mac1}")
            print(f"设备2 ({self.ser2.port}): {mac2}")

            # ===== 2. 恢复出厂设置 =====
            if not self.factory_reset(self.ser1):
                print("❌ 设备1恢复出厂设置失败")
                return False

            if not self.factory_reset(self.ser2):
                print("❌ 设备2恢复出厂设置失败")
                return False

            # ===== 3. 配置设备角色 =====
            # 设备1作为主机
            if not self.set_role(self.ser1, 1):
                print("❌ 设备1设置为主机失败")
                return False

            # 设备2作为从机
            if not self.set_role(self.ser2, 0):
                print("❌ 设备2设置为从机失败")
                return False

            # 配置从机参数
            if not self.enable_broadcast(self.ser2):
                print("❌ 启用从机广播失败")
                return False

            # if not self.set_tx_power(self.ser2, 4):  # 最大功率
            #     print("⚠️ 设置发射功率失败，继续流程")

            # ===== 4. 扫描并连接 =====
            print("\n=== 扫描阶段 ===")
            scanned_macs = self.scan_devices(self.ser1)
            # if mac2 not in [mac[0] for mac in scanned_macs]:
            #     print(f"❌ 未找到目标设备 {mac2}")
            #     return False

            print("\n=== 连接阶段 ===")
            if not self.connect_to_device(self.ser1,mac2):
                return False

            # ===== 5. 启用透传模式 =====
            print("\n=== 主从透传模式 ===")
            if not self.enable_transparent_mode(self.ser1):
                print("⚠️ 透传模式启用失败，但连接已建立")
            if not self.enable_transparent_mode(self.ser2):
                print("⚠️ 透传模式启用失败，但连接已建立")
            return True

        except Exception as e:
            print(f"\n❌ 未处理错误: {str(e)}")
            return False

    def close(self):
        """关闭所有连接"""
        if self.ser1:
            self.ser1.close()
        if self.ser2:
            self.ser2.close()


def select_serial_port(prompt):
    """用户选择串口设备"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ 未检测到可用串口")
        return None

    print("\n🔍 可用串口设备:")
    for i, port in enumerate(ports, 1):
        print(f"{i}. {port.device} - {port.description}")

    try:
        selection = int(input(prompt))
        if 1 <= selection <= len(ports):
            return ports[selection - 1].device
        print("❌ 选择超出范围")
    except ValueError:
        print("❌ 请输入有效数字")
    return None


if __name__ == "__main__":
    print("=" * 60)
    print("EWM104-BT57U成对使用配置工具_V1.6")
    print("=" * 60)
    print("——EBYTE-huangzhechuan")

    # 用户选择串口
    host_port = select_serial_port("\n请选择主机设备序号: ")
    if not host_port:
        sys.exit(1)

    slave_port = select_serial_port("请选择从机设备序号: ")
    if not slave_port:
        sys.exit(1)

    # 创建配对器
    pairer = BlePairer(host_port, slave_port)

    # 执行配对
    print("\n" + "=" * 30 + " 开始配对 " + "=" * 30)
    if pairer.auto_pair():
        print("\n🎉 配对成功! 设备已连接并进入透传模式")

        # # 显示连接状态（根据文档4.5节）
        # print("\n设备状态:")
        # print(" - 主机LINK指示灯应常亮（红色）")
        # print(" - 从机LINK指示灯应常亮（绿色）")

        # # 显示产品图片
        # print("\n产品外观参考:")
        # print("主机设备:")
        #
        # print("\n从机设备:")

    else:
        print("\n❌ 配对失败，请检查以下可能原因:")
        print("1. 设备间距过远---")
        print("2. 供电电压不足---")
        print("3. 存在同频干扰---")

    # 清理资源
    pairer.close()
    print("\n🔚 程序结束")