import serial
import serial.tools.list_ports
import traceback
import threading


def open_serial_port(port_name, baudrate=115200):  # 修改默认波特率为115200
    """
    打开指定串口
    :param port_name: 串口号 (如 '/dev/cu.usbserial-120')
    :param baudrate: 波特率 (默认115200)
    :return: 串口对象 (成功) 或 None (失败)
    """
    try:
        ser = serial.Serial(
            port=port_name,
            baudrate=baudrate,  # 使用115200波特率
            bytesize=serial.EIGHTBITS,  # 数据位8
            parity=serial.PARITY_NONE,  # 校验位无
            stopbits=serial.STOPBITS_ONE,  # 停止位1
            timeout=0.5
        )
        print(f"串口 {port_name} 已成功打开 (波特率: {baudrate})")  # 添加波特率显示
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


def read_from_serial(ser, name):
    """从指定串口读取数据的线程函数"""
    try:
        while True:
            if ser.in_waiting:
                response = ser.readline().decode().strip()
                if response:
                    print(f"[{name} 接收]: {response}")
    except Exception as e:
        print(f"[{name} 读取错误]: {e}")


def test_dual_serial_communication(host_ser, slave_ser):
    """测试两个串口之间的通信"""
    if not host_ser or not host_ser.is_open or not slave_ser or not slave_ser.is_open:
        print("串口未正确打开")
        return

    # 启动读取线程
    host_thread = threading.Thread(target=read_from_serial, args=(host_ser, "主机"), daemon=True)
    slave_thread = threading.Thread(target=read_from_serial, args=(slave_ser, "从机"), daemon=True)

    host_thread.start()
    slave_thread.start()

    print("\n串口通信测试开始 (输入 'exit' 退出)")
    print("选择发送端口: 1=主机, 2=从机")

    while True:
        try:
            command = input("> ")
            if command.lower() == 'exit':
                break

            # 解析命令格式: <端口选择> <消息内容>
            if ' ' in command:
                port_choice, message = command.split(' ', 1)

                if port_choice == '1':
                    host_ser.write((message + '\n').encode())
                    print(f"[主机 发送]: {message}")
                elif port_choice == '2':
                    slave_ser.write((message + '\n').encode())
                    print(f"[从机 发送]: {message}")
                else:
                    print("无效的端口选择，请使用 1 或 2")
            else:
                print("命令格式错误，请使用: <端口> <消息>")

        except Exception as e:
            print(f"通信错误: {e}")
            break


if __name__ == "__main__":
    # 列出所有可用串口
    available_ports = list_serial_ports()
    if not available_ports:
        exit()

    # 让用户选择两个串口
    print("\n请选择要打开的串口 (输入序号)")
    for i, port in enumerate(available_ports):
        print(f"{i}: {port}")

    try:
        # 选择主机串口
        print("\n选择主机串口:")
        host_choice = int(input("> "))
        host_port = available_ports[host_choice]

        # 选择从机串口
        print("\n选择从机串口:")
        slave_choice = int(input("> "))
        slave_port = available_ports[slave_choice]

        if host_port == slave_port:
            print("错误: 不能选择同一个串口作为主机和从机")
            exit()

    except (ValueError, IndexError):
        print("无效的选择")
        exit()


    except KeyboardInterrupt:
        print("手动退出程序")

    # 打开两个串口
    print("\n打开主机串口...")
    host_ser = open_serial_port(host_port)
    print("\n打开从机串口...")
    slave_ser = open_serial_port(slave_port)

    if not host_ser or not slave_ser:
        print("无法打开串口，程序退出")
        close_serial_port(host_ser)
        close_serial_port(slave_ser)
        exit()

    # 测试双串口通信
    test_dual_serial_communication(host_ser, slave_ser)

    # 关闭串口
    close_serial_port(host_ser)
    close_serial_port(slave_ser)