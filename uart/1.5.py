import serial
import serial.tools.list_ports
import time
import re
import threading


class BlePairer:
    def __init__(self, port1=None, port2=None, baudrate=115200, timeout=2):
        self.baudrate = baudrate
        self.timeout = timeout
        self.mac_cache = {}
        self.original_ports = {}  # 记录原始端口信息

        # 自动检测并打开串口
        self.ser1 = self.open_serial(port1) if port1 else None
        self.ser2 = self.open_serial(port2) if port2 else None

        # 记录原始端口信息
        if self.ser1:
            self.original_ports["ser1"] = self.ser1.port
        if self.ser2:
            self.original_ports["ser2"] = self.ser2.port

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

    def reconnect_serial(self, ser, original_port):
        """重新连接串口（设备重启后）"""
        if ser and ser.is_open:
            ser.close()
            print(f"已关闭串口: {original_port}")

        print(f"等待设备 {original_port} 重启...")
        time.sleep(3)  # 等待设备重启完成

        # 尝试重新打开原始端口
        try:
            print(f"尝试重新打开串口: {original_port}")
            new_ser = serial.Serial(original_port, self.baudrate, timeout=self.timeout)
            print(f"成功重新打开串口: {original_port}")
            return new_ser
        except serial.SerialException as e:
            print(f"重新打开串口 {original_port} 失败: {str(e)}")

            # 如果原始端口打开失败，尝试重新扫描端口
            print("尝试扫描可用串口...")
            available_ports = self.list_serial_ports()
            if not available_ports:
                print("无可用串口设备")
                return None

            # 尝试匹配原始端口描述
            for port_info in available_ports:
                if original_port in port_info:
                    print(f"尝试使用匹配的串口: {port_info}")
                    try:
                        new_ser = serial.Serial(port_info, self.baudrate, timeout=self.timeout)
                        print(f"成功打开串口: {port_info}")
                        return new_ser
                    except:
                        continue

            print("无法重新连接串口，请手动检查设备")
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

    def send_at_command(self, ser, command, expected_response=None, retries=3):
        """发送AT指令并获取响应"""
        if not ser or not ser.is_open:
            print(f"串口 {ser.port if ser else '未知'} 未打开")
            return ""

        for attempt in range(retries):
            try:
                # 清除接收缓冲区
                ser.reset_input_buffer()

                # 发送命令
                ser.write((command + "\r\n").encode())
                print(f"[{ser.port}] 发送: {command}")

                # 等待响应
                response = ""
                start_time = time.time()
                while time.time() - start_time < self.timeout:
                    if ser.in_waiting:
                        response += ser.read(ser.in_waiting).decode()
                        if '\n' in response:  # 检测到换行符，可能是完整响应
                            break
                    time.sleep(0.1)

                response = response.strip()
                print(f"[{ser.port}] 接收: {response}")

                # 检查预期响应
                if expected_response:
                    if expected_response in response:
                        return response
                    elif attempt < retries - 1:
                        print(f"未收到预期响应，重试中 ({attempt + 1}/{retries})...")
                        time.sleep(0.5)
                        continue
                    else:
                        print(f"未收到预期响应: {expected_response}")
                        return response
                else:
                    return response

            except serial.SerialException as e:
                if attempt < retries - 1:
                    print(f"串口通信错误: {str(e)}，重试中 ({attempt + 1}/{retries})...")
                    time.sleep(1)
                else:
                    print(f"串口通信错误: {str(e)}")
                    return ""

        return ""

    def get_mac_address(self, ser):
        """获取设备MAC地址"""
        if not ser:
            return None

        if ser.port in self.mac_cache:
            return self.mac_cache[ser.port]

        response = self.send_at_command(ser, "AT+MAC?", expected_response="MAC=")

        if "MAC=" in response:
            mac = response.split('=')[1].strip()
            self.mac_cache[ser.port] = mac
            return mac
        else:
            print(f"获取MAC地址失败，响应: {response}")
            return None

    def configure_device(self, ser, role, original_port):
        """配置设备角色（0=从机, 1=主机）并处理重启"""
        # 设置角色
        # self.send_at_command(ser ,"AT+RESTORE")
        # time.sleep(0.15)
        # self.reconnect_serial(ser, original_port)

        self.send_at_command(ser, f"AT+ROLE={role}", expected_response="+OK")
        self.send_at_command(ser,"AT+SCAN?")

        # 如果是从机，还需要设置广播参数
        if role == 0:
            self.send_at_command(ser, "AT+ADV=1,1,200", expected_response="+OK")

        # 发送重启命令
        print(f"[{ser.port}] 发送重启命令...")
        self.send_at_command(ser, "AT+RESET")

        # 重新连接串口         5
        return self.reconnect_serial(ser, original_port)

    def connect_device(self, host_ser, slave_mac):
        """主机连接从机"""
        # 发送连接命令
        response = self.send_at_command(host_ser, f"AT+CONNECT={slave_mac}", expected_response="+OK")
        if not response:
            return False


        # 等待连接成功状态
        print(f"[{host_ser.port}] 正在连接设备 {slave_mac}...")
        start_time = time.time()
        while time.time() - start_time < 15:
            try:
                if host_ser.in_waiting:
                    status = host_ser.read(host_ser.in_waiting).decode()
                    if "CONNECT" in status:
                        print(f"[{host_ser.port}] 连接状态: {status.strip()}")
                        return True
                time.sleep(1)
            except serial.SerialException as e:
                print(f"连接过程中发生错误: {str(e)}")
                return False

        print("连接超时")
        return False

    def auto_pair(self):
        """自动配对主逻辑"""
        try:
            # 获取设备信息
            mac1 = self.get_mac_address(self.ser1)
            mac2 = self.get_mac_address(self.ser2)
            if not mac1 or not mac2:
                raise Exception("无法获取一个或两个设备的MAC地址")

            print(f"\n=== 设备信息 ===")
            print(f"设备1 ({self.ser1.port}) MAC: {mac1}")
            print(f"设备2 ({self.ser2.port}) MAC: {mac2}")

            # 配置设备1为主机
            print("\n配置设备1为主机...")
            new_ser1 = self.configure_device(self.ser1, 1, self.original_ports.get("ser1", self.ser1.port))
            if not new_ser1:
                raise Exception("设备1配置失败")
            self.ser1 = new_ser1

            # 配置设备2为从机
            print("\n配置设备2为从机...")
            new_ser2 = self.configure_device(self.ser2, 0, self.original_ports.get("ser2", self.ser2.port))
            if not new_ser2:
                raise Exception("设备2配置失败")
            self.ser2 = new_ser2

            # 重新获取MAC地址（设备重启后可能需要重新获取）
            self.mac_cache.clear()
            mac1 = self.get_mac_address(self.ser1)
            mac2 = self.get_mac_address(self.ser2)

            # 主机连接从机
            print("\n主机开始连接从机...")
            if not self.connect_device(self.ser1, mac2):
                raise Exception("连接失败")

            # 验证连接状态
            print("\n验证连接状态...")
            time.sleep(2)
            host_status = self.send_at_command(self.ser1, "AT+CONNECT_LIST?")
            slave_status = self.send_at_command(self.ser2, "AT+CONNECT_LIST?")

            if mac2 in host_status and mac1 in slave_status:
                print("\n连接状态验证成功!")
                return True
            else:
                print("\n连接状态验证失败!")
                return False

        except Exception as e:
            print(f"\n[错误] {str(e)}")
            return False

    def auto_send(self):
        respones = self.send_at_command(self.ser1, "AT+TRM_HANDLE?")
        return True



    def close_all(self):
        """关闭所有串口连接"""
        if self.ser1 and self.ser1.is_open:
            self.ser1.close()
            print(f"已关闭串口: {self.ser1.port}")
        if self.ser2 and self.ser2.is_open:
            self.ser2.close()
            print(f"已关闭串口: {self.ser2.port}")


if __name__ == "__main__":
    print("===== BLE设备一键配对脚本--EBYTE =====")
    print("===== huangzhechuan_2025.7.15_v1.0 =====")

    # 1. 列出所有可用串口
    available_ports = BlePairer.list_serial_ports()
    if not available_ports:
        print("未找到可用串口，程序退出")
        exit(1)

    # 2. 让用户选择两个串口
    try:
        port1 = int(input("请输入第一个设备序号: ").strip())
        port2 = int(input("请输入第二个设备序号: ").strip())
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

        print("\n===== 开始建立绑定mac透传 =====")
        if pairer.auto_send():
            print("\n[成功] 绑定mac透传成功!")
        else:
            print("\n[失败] 绑定mac透传失败，请检查设备和连接")

    # except KeyboardInterrupt:
    #     pairer.close_all()
    #     print("程序结束")

    except Exception as e:
        print(f"\n[错误] 发生未预期错误: {str(e)}")
    finally:
        pairer.close_all()
        print("程序结束")