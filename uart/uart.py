import serial
import serial.tools.list_ports
import traceback


def open_serial_port(port_name, baudrate=9600):
    """
    打开指定串口
    :param port_name: 串口号 (如 '/dev/cu.usbserial-120')
    :param baudrate: 波特率 (默认9600)
    :return: 串口对象 (成功) 或 None (失败)
    """
    try:
        ser = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5
        )
        print(f"串口 {port_name} 已成功打开")
        return ser
    except Exception as e:
        print(f"打开串口 {port_name} 失败: {e}")
        traceback.print_exc()
        return None


def close_serial_port(ser):
    """关闭串口"""
    if ser and ser.is_open:
        ser.close()
        print(f"串口 {ser.port} 已关闭")


def list_serial_ports():
    """列出所有可用串口"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("无串口设备。")
        return []

    print("可用的串口设备:")
    return [port.device for port in ports]


def test_serial_communication(ser):
    """测试串口通信"""
    if not ser or not ser.is_open:
        print("串口未打开")
        return

    print("\n输入要发送的数据 (输入 'exit' 退出):")
    while True:
        data = input("> ")
        if data.lower() == 'exit':
            break

        try:
            # 发送数据
            ser.write(data.encode())
            print(f"发送: {data}")

            # 接收数据
            response = ser.readline().decode().strip()
            if response:
                print(f"接收: {response}")
            else:
                print("未收到响应")

        except Exception as e:
            print(f"通信错误: {e}")
            break


if __name__ == "__main__":
    # 列出所有可用串口
    available_ports = list_serial_ports()
    if not available_ports:
        exit()

    # 让用户选择串口
    print("\n请选择要打开的串口 (输入序号):")
    for i, port in enumerate(available_ports):
        print(f"{i}: {port}")

    try:
        choice = int(input("> "))
        selected_port = available_ports[choice]
    except (ValueError, IndexError):
        print("无效的选择")
        exit()

    # 打开串口
    ser = open_serial_port(selected_port)
    if not ser:
        exit()

    # 测试串口通信
    test_serial_communication(ser)

    # 关闭串口
    close_serial_port(ser)