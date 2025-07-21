import serial
import time
import re


class BlePairer:
    def __init__(self, port1, port2, baudrate=115200, timeout=2):
        self.ser1 = serial.Serial(port1, baudrate, timeout=timeout)
        self.ser2 = serial.Serial(port2, baudrate, timeout=timeout)
        self.mac_cache = {}  # 存储设备MAC地址缓存

    def list_serial_ports(self):
        """列出所有可用串口"""
        ports = serial.tools.list_ports.comports()
        if not ports:
            print("无串口设备即将退出程序。")
            return []

        print("可用的串口设备:")
        return [port.device for port in ports]

    def send_at_command(self, ser, command):
        """发送AT指令并获取响应"""
        ser.write((command + "\r\n").encode())
        time.sleep(0.5)
        response = ser.read(ser.in_waiting).decode().strip()
        print(f"[{ser.port}] Send: {command} -> Recv: {response}")
        return response

    def get_mac_address(self, ser):
        """获取设备MAC地址"""
        if ser.port in self.mac_cache:
            return self.mac_cache[ser.port]

        response = self.send_at_command(ser, "AT+MAC?")
        if "MAC=" in response:
            mac = response.split('=')[1]
            self.mac_cache[ser.port] = mac
            return mac
        raise Exception("MAC address not found")

    def setup_role(self, ser, role):
        """设置设备角色（0=从机, 1=主机）"""
        response = self.send_at_command(ser, f"AT+ROLE={role}")
        if "+OK" not in response:
            raise Exception(f"Set role failed: {response}")
        return True

    def enable_broadcast(self, ser):
        """开启从机广播"""
        responses = [
            self.send_at_command(ser, "AT+ADV=1,1,200"),
            self.send_at_command(ser, "AT+ADV?")
        ]
        return all("+ADV=1,1,200" in r for r in responses)

    def scan_devices(self, ser):
        """主机扫描从机设备"""
        self.send_at_command(ser, "AT+SCAN=1,10,0")
        scan_data = ""
        start_time = time.time()

        while time.time() - start_time < 12:  # 12秒超时
            scan_data += ser.read(ser.in_waiting).decode()
            time.sleep(1)
            if "SCAN=1,10,0" in scan_data:
                break

        print(f"[{ser.port}] Scan results:\n{scan_data}")
        return re.findall(r"(\w{2}:\w{2}:\w{2}:\w{2}:\w{2}:\w{2})", scan_data)

    def connect_device(self, ser, mac):
        """主机连接从机"""
        response = self.send_at_command(ser, f"AT+CONNECT=,{mac}")
        if "+OK" not in response:
            return False

        # 等待连接成功状态
        start_time = time.time()
        while time.time() - start_time < 15:  # 15秒超时
            status = ser.read(ser.in_waiting).decode()
            if "CONNECT" in status:
                print(f"[{ser.port}] Connection status: {status.strip()}")
                return True
            time.sleep(1)
        return False

    def auto_pair(self):
        """自动配对主逻辑"""
        try:
            # 获取设备信息
            mac1 = self.get_mac_address(self.ser1)
            mac2 = self.get_mac_address(self.ser2)
            print(f"\n=== Device Info ===\nPort1 ({self.ser1.port}) MAC: {mac1}\nPort2 ({self.ser2.port}) MAC: {mac2}")

            # 第一次尝试：ser1作为主机，ser2作为从机
            print("\n=== Attempt 1: Port1 as Host ===")
            if (
                    self.setup_role(self.ser1, 1) and
                    self.setup_role(self.ser2, 0) and
                    self.enable_broadcast(self.ser2)
            ):
                scanned_macs = self.scan_devices(self.ser1)
                if mac2 in scanned_macs and self.connect_device(self.ser1, mac2):
                    return True

            # 第二次尝试：ser2作为主机，ser1作为从机
            print("\n=== Attempt 2: Port2 as Host ===")
            if (
                    self.setup_role(self.ser2, 1) and
                    self.setup_role(self.ser1, 0) and
                    self.enable_broadcast(self.ser1)
            ):
                scanned_macs = self.scan_devices(self.ser2)
                if mac1 in scanned_macs and self.connect_device(self.ser2, mac1):
                    return True

            raise Exception("All pairing attempts failed")

        except Exception as e:
            print(f"\n[Error] {str(e)}")
            return False
        finally:
            self.ser1.close()
            self.ser2.close()


if __name__ == "__main__":
    BlePairer.list_serial_ports()