import serial
import serial.tools.list_ports
import time
import re


class BlePairer:
    def __init__(self, port1=None, port2=None, baudrate=115200, timeout=2):
        self.baudrate = baudrate
        self.timeout = timeout
        self.mac_cache = {}

        # 自动检测并打开串口
        self.ser1 = self.open_serial(port1) if port1 else None
        self.ser2 = self.open_serial(port2) if port2 else None

    def open_serial(self, port):
        """安全打开串口连接"""
        try:
            # 检查端口格式，如果是数字则转换为实际设备路径
            if isinstance(port, int):
                ports = BlePairer.list_serial_ports()
                if 1 <= port <= len(ports):
                    port = ports[port - 1]
                else:
                    print(f"错误：无效的端口序号 {port}")
                    return None

            ser = serial.Serial(port, self.baudrate, timeout=self.timeout)
            print(f"成功打开串口: {port}")
            return ser
        except serial.SerialException as e:
            print(f"打开串口 {port} 失败: {str(e)}")
            return None

    @staticmethod
    def list_serial_ports():
        """列出所有可用串口"""
        ports = serial.tools.list_ports.comports()
        if not ports:
            print("无可用串口设备")
            return []

        print("可用的串口设备:")
        for i, port in enumerate(ports):
            print(f"{i + 1}. {port.device} - {port.description}")
        return [port.device for port in ports]

    def send_at_command(self, ser, command):
        """发送AT指令并获取响应"""
        if not ser or not ser.is_open:
            print(f"串口 {ser.port if ser else '未知'} 未打开")
            return ""

        try:
            # 清除接收缓冲区
            ser.reset_input_buffer()

            # 发送命令
            ser.write((command + "\r\n").encode())

            # 等待响应
            time.sleep(0.5)
            response = ser.read(ser.in_waiting).decode().strip()
            print(f"[{ser.port}] 发送: {command} → 接收: {response}")
            return response
        except serial.SerialException as e:
            print(f"串口通信错误: {str(e)}")
            return ""

    def get_mac_address(self, ser):
        """获取设备MAC地址"""
        if not ser:
            return None

        if ser.port in self.mac_cache:
            return self.mac_cache[ser.port]

        response = self.send_at_command(ser, "AT+MAC?")

        if "MAC=" in response:
            mac = response.split('=')[1].strip()
            self.mac_cache[ser.port] = mac
            return mac
        else:
            print(f"获取MAC地址失败，响应: {response}")
            return None

    def setup_role(self, ser, role):
        """设置设备角色（0=从机, 1=主机）"""
        response = self.send_at_command(ser, f"AT+ROLE={role}")
        self.send_at_command(ser, "AT+RESET")
        self.ser1.is_open()

        if "+OK" not in response:
            raise Exception(f"设置角色失败: {response}")
        return True

    # def enable_broadcast(self, ser):
    #     """开启从机广播"""
    #     self.send_at_command(ser, "AT+ADV=1,1,200")  # 先开启广播
    #     self.send_at_command(ser, "AT+RESET")

    def connect_device(self, ser, mac):
        """主机连接从机"""
        response = self.send_at_command(ser, f"AT+CONNECT=,{mac}")
        if "+OK" not in response:
            return False
        # 等待连接成功状态
        print(f"[{ser.port}] 正在连接设备 {mac}...")
        start_time = time.time()
        while time.time() - start_time < 15:
            status = ser.read(ser.in_waiting).decode()
            if "CONNECT" in status:
                print(f"[{ser.port}] 连接状态: {status.strip()}")
                return True
            time.sleep(1)
        return False

    def auto_pair(self):
        """自动配对主逻辑"""
        try:
            # 获取设备信息
            mode1 = self.setup_role(self.ser1,1)
            mode2 = self.setup_role(self.ser1,0)
            mac1 = self.get_mac_address(self.ser1)
            mac2 = self.get_mac_address(self.ser2)
            if not mac1 or not mac2:
                raise Exception("无法获取一个或两个设备的MAC地址")

            print(f"\n=== 设备信息 ===\n设备1 ({self.ser1.port}) MAC: {mac1}\n设备2 ({self.ser2.port}) MAC: {mac2}")

            self.connect_device(self.ser1,mac2)

        except Exception as e:
            print(f"\n[错误] {str(e)}")
            return False




    def close_all(self):
        """关闭所有串口连接"""
        if self.ser1 and self.ser1.is_open:
            self.ser1.close()
            print(f"已关闭串口: {self.ser1.port}")
        if self.ser2 and self.ser2.is_open:
            self.ser2.close()
            print(f"已关闭串口: {self.ser2.port}")


if __name__ == "__main__":
    print("===== BLE设备一键配对工具 =====")

    # 1. 列出所有可用串口
    available_ports = BlePairer.list_serial_ports()
    if not available_ports:
        print("未找到可用串口，程序退出")
        exit(1)

    # 2. 让用户选择两个串口
    try:
        port1 = int(input("请输入第一个设备序号 : ").strip())
        port2 = int(input("请输入第二个设备序号 : ").strip())
    except ValueError:
        print("错误：请输入数字序号")
        exit(1)

    # 3. 创建配对器实例
    pairer = BlePairer(port1=port1, port2=port2)

    # 检查串口是否成功打开
    if not pairer.ser1 or not pairer.ser2:
        print("无法打开串口，程序退出")
        exit(1)

    try:
        print("\n===== 开始配对 =====")
        if pairer.auto_pair():
            print("\n[成功] 设备配对成功!")
        else:
            print("\n[失败] 配对失败，请检查设备和连接")
    except Exception as e:
        print(f"\n[错误] 发生未预期错误: {str(e)}")
    finally:
        pairer.close_all()
        print("程序结束")