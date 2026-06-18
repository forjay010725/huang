#!/usr/bin/env python3
"""
使用PyInstaller将Python脚本打包为独立可执行文件
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime

# *************** 配置参数 ***************
APP_NAME = "BLE_Pairing_Tool"
MAIN_SCRIPT = "ble_pair_tool.py"  # 主脚本文件名
VERSION = "1.6"
AUTHOR = "EBYTE-huangzhechuan"
ICON_FILE = "app_icon.ico"  # 应用图标文件
ADDITIONAL_FILES = []  # 需要包含的额外文件
EXCLUDE_MODULES = []  # 要排除的模块
INCLUDE_MODULES = ["serial", "serial.tools"]  # 要包含的模块
CONSOLE = True  # 是否显示控制台窗口
ONE_FILE = True  # 打包为单个文件


# **************************************

def build_executable():
    """直接调用PyInstaller构建可执行文件"""
    # 创建构建命令
    cmd = [
        sys.executable,  # 使用当前Python解释器
        "-m", "PyInstaller",
        "--name", APP_NAME,
        "--clean",
    ]

    # 添加单文件选项
    if ONE_FILE:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # 添加控制台选项
    if CONSOLE:
        cmd.append("--console")
    else:
        cmd.append("--windowed")

    # 添加图标文件
    if ICON_FILE and os.path.exists(ICON_FILE):
        cmd.extend(["--icon", ICON_FILE])

    # 添加Windows版本信息
    if sys.platform == "win32" and os.path.exists("version_info.txt"):
        cmd.extend(["--version-file", "version_info.txt"])

    # 添加隐藏导入
    for module in INCLUDE_MODULES:
        cmd.extend(["--hidden-import", module])

    # 添加排除模块
    for module in EXCLUDE_MODULES:
        cmd.extend(["--exclude-module", module])

    # 添加主脚本文件
    cmd.append(MAIN_SCRIPT)

    print("🚀 开始打包应用...")
    print("执行命令:", " ".join(cmd))

    try:
        result = subprocess.run(cmd, check=True)
        if result.returncode == 0:
            print(f"✅ 应用打包成功！输出目录: dist/{APP_NAME}")
            return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 打包失败: {str(e)}")
        return False
    except FileNotFoundError:
        print("❌ 找不到PyInstaller模块，请确保已安装: pip install pyinstaller")
        return False


def create_version_file():
    """创建Windows版本信息文件"""
    if sys.platform != "win32":
        return

    # 将版本号转换为元组格式 (1, 6, 0, 0)
    version_parts = VERSION.split('.')
    version_tuple = tuple(map(int, version_parts)) + (0,) * (4 - len(version_parts))

    version_content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x4,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', '{AUTHOR}'),
        StringStruct('FileDescription', '{APP_NAME}'),
        StringStruct('FileVersion', '{VERSION}'),
        StringStruct('InternalName', '{APP_NAME}'),
        StringStruct('LegalCopyright', 'Copyright © {datetime.now().year} {AUTHOR}'),
        StringStruct('OriginalFilename', '{APP_NAME}.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{VERSION}')])
      ]), 
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    version_path = "version_info.txt"
    with open(version_path, "w", encoding="utf-8") as f:
        f.write(version_content)
    print(f"ℹ️ 已创建Windows版本信息文件: {version_path}")


def create_installer():
    """创建安装包（仅Windows）"""
    if sys.platform != "win32":
        print("⚠️ 安装包创建仅支持Windows系统")
        return

    print("📦 创建安装包...")

    # 构建安装包内容
    app_exe = f"{APP_NAME}.exe"
    output_base = f"{APP_NAME}_Setup_{VERSION}"

    iss_content = f"""; Inno Setup 脚本
[Setup]
AppId={{{APP_NAME.upper()}-{VERSION.replace('.', '-')}}}
AppName={APP_NAME}
AppVersion={VERSION}
AppPublisher={AUTHOR}
AppPublisherURL=https://www.ebyte.com/
DefaultDirName={{autopf}}\\{APP_NAME}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename={output_base}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面图标"; GroupDescription: "附加图标:"; Flags: unchecked

[Files]
Source: "dist\\{app_exe}"; DestDir: "{{app}}"; Flags: ignoreversion
"""

    # 添加图标文件
    if ICON_FILE and os.path.exists(ICON_FILE):
        iss_content += f"Source: \"{ICON_FILE}\"; DestDir: \"{{app}}\"; Flags: ignoreversion\n"

    # 添加其他文件
    iss_content += """
[Icons]
Name: "{autoprograms}\{APP_NAME}"; Filename: "{app}\{app_exe}"
Name: "{autodesktop}\{APP_NAME}"; Filename: "{app}\{app_exe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{app_exe}"; Description: "运行应用程序"; Flags: nowait postinstall skipifsilent
"""

    iss_path = f"{APP_NAME}_installer.iss"
    with open(iss_path, "w", encoding="utf-8") as f:
        f.write(iss_content)
    print(f"ℹ️ 已创建Inno Setup脚本: {iss_path}")

    # 查找Inno Setup编译器
    inno_path = None
    possible_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            inno_path = path
            break

    if not inno_path:
        print("❌ 未找到Inno Setup，请先安装: https://jrsoftware.org/isdl.php")
        return

    # 执行Inno Setup编译
    try:
        print(f"🔨 正在使用Inno Setup编译安装包: {inno_path}")
        result = subprocess.run([inno_path, iss_path], check=True)
        if result.returncode == 0:
            print(f"✅ 安装包创建成功！位置: installer/{output_base}.exe")
    except FileNotFoundError:
        print(f"❌ 找不到Inno Setup编译器: {inno_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ 安装包创建失败: {str(e)}")


def main():
    """主打包流程"""
    print(f"🔧 {APP_NAME} 打包工具 v{VERSION}")
    print("=" * 60)

    # 检查主脚本是否存在
    if not os.path.exists(MAIN_SCRIPT):
        print(f"❌ 主脚本文件不存在: {MAIN_SCRIPT}")
        return

    # 创建版本信息文件（Windows）
    if sys.platform == "win32":
        create_version_file()

    # 清理旧构建文件
    print("🧹 清理旧构建文件...")
    if os.path.exists("build"):
        shutil.rmtree("build", ignore_errors=True)
    if os.path.exists("dist"):
        shutil.rmtree("dist", ignore_errors=True)

    # 确保dist目录存在
    os.makedirs("dist", exist_ok=True)

    # 执行打包
    if build_executable():
        # 复制额外文件到dist目录
        if ADDITIONAL_FILES:
            print("📁 复制额外文件到dist目录...")
            for file in ADDITIONAL_FILES:
                if os.path.exists(file):
                    shutil.copy(file, "dist")
                    print(f"  - 已复制: {file}")

        # 创建安装包（Windows）
        if sys.platform == "win32":
            create_installer()

        print("\n🎉 打包完成！")
        print(f"可执行文件位置: dist/{APP_NAME}.exe")
        if sys.platform == "win32":
            print(f"安装包位置: installer/{APP_NAME}_Setup_{VERSION}.exe")
    else:
        print("\n❌ 打包失败，请检查错误信息")


if __name__ == "__main__":
    main()
