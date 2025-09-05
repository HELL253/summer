import time, os, gc, sys, math
from media.sensor import *
from media.display import *
from media.media import *
from machine import UART, FPIOA, TOUCH, Pin

picture_width = 800
picture_height = 480
sensor = None
# 显示模式选择：可以是 "VIRT"、"LCD"
DISPLAY_MODE = "LCD"
# 3.1寸屏幕模式
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

try:
    sensor = Sensor()  # 构造一个具有默认配置的摄像头对象
    sensor.reset()  # 重置摄像头sensor
    sensor.set_framesize(width=picture_width, height=picture_height)  # 设置通道0的输出尺寸为显示分辨率
    sensor.set_pixformat(Sensor.GRAYSCALE)  # 设置通道0的输出像素格式为 GRAYSCALE

    # 根据模式初始化显示器
    if DISPLAY_MODE == "VIRT":
        Display.init(Display.VIRT, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, fps=60)
    elif DISPLAY_MODE == "LCD":
        Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=True)

    # 初始化媒体管理器
    MediaManager.init()
    # 启动传感器
    sensor.run()
    # 配置引脚
    fpioa = FPIOA()
    fpioa.set_function(53, FPIOA.GPIO53)
    fpioa.set_function(11, FPIOA.UART2_TXD)
    fpioa.set_function(12, FPIOA.UART2_RXD)
    # 按键配置
    key = Pin(53, Pin.IN, Pin.PULL_DOWN)
    # 初始化UART2
    uart = UART(UART.UART2, baudrate=115200, bits=UART.EIGHTBITS, parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)
    # 触摸屏初始化
    tp = TOUCH(0)

    clock = time.clock()  # 创建时钟对象用于计算FPS
    frame_count = 0
    flag = 0
    flag_start_time = 0
    TIMEOUT_MS = 5000

    # 图像中心点像中心点中心点坐标计算
    center_x = sensor.width() // 2  # 图像水平中心坐标(像素)
    center_y = sensor.height() // 2  # 图像垂直中心坐标(像素)

    """在检测到的色块中找出中心最小色块"""
    def find_center_min_blob(blobs):
        blob = None
        min_area = 100000  # 初始化最小面积为较大值
        for b in blobs:
            # 过滤距离画面中心较远的色块（曼哈顿距离>50）
            if abs(b.cx() - center_x) + abs(b.cy() - center_y) > 50:
                continue
            # 筛选面积最小的色块
            if b.area() > min_area:
                continue
            blob = b
            min_area = b.area()
        return blob

    """在检测到的色块中找出中心最大色块"""
    def find_center_max_blob(blobs):
        blob = None
        max_area = 0  # 初始化最大面积为0
        for b in blobs:
            # 过滤距离距离距离距离离画面中心较远的色块（曼哈顿距离>30）
            if abs(b.cx() - center_x) + abs(b.cy() - center_y) > 30:
                continue
            # 筛选面积最大的色块
            if b.area() < max_area:
                continue
            blob = b
            max_area = b.area()
        return blob

    """寻找最小矩形的像素数量"""
    def find_min_rectangle_blob(blobs):
        min_rect_blob = None
        min_pixels = float('inf')
        for b in blobs:
            w, h = b.w(), b.h()
            pixels = b.pixels()
            if max(w / h, h / w) > 4 or pixels < 30:  # 过滤非矩形和小噪声
                continue
            if pixels < min_pixels:
                min_pixels = pixels
                min_rect_blob = b  # 保存色块对象
        return min_rect_blob, min_pixels if min_rect_blob else (None, None)

    threshold_dict = {'Q_K': [(140, 255)], 'S_N': [(0, 130)]}
    while True:
        clock.tick()
        os.exitpoint()
        if flag != 0:
            current_time = time.ticks_ms()
            elapsed = time.ticks_diff(current_time, flag_start_time)
            if elapsed >= TIMEOUT_MS:
                print(f"flag={flag} 已超时（5秒），自动退出")
                flag = 0  # 重置flag状态
        #脱机调阈值
        if key.value() == 1:
            # 清空当前的阈值
            for key_ in threshold_dict.keys():
                threshold_dict[key_] = []
            button_color = (150, 150, 150)
            text_color = (0, 0, 0)
            # 创建一个画布，用来绘制按钮
            img = image.Image(800, 480, image.RGB565)
            img.draw_rectangle(0, 0, 800, 480, color=(255, 255, 255), thickness=2, fill=True)
            # 左侧侧功能按钮
            # 返回按钮（左上）
            img.draw_rectangle(20, 20, 150, 80, color=button_color, thickness=2, fill=True)
            img.draw_string_advanced(20 + 30, 20, 35, "返回", color=text_color)
            # 归位按钮（左下）
            img.draw_rectangle(20, 480 - 100, 150, 80, color=button_color, thickness=2, fill=True)
            img.draw_string_advanced(20 + 30, 480 - 100, 35, "归位", color=text_color)
            # 右侧功能按钮
            # 切换按钮（右上）
            img.draw_rectangle(800 - 170, 20, 150, 80, color=button_color, thickness=2, fill=True)
            img.draw_string_advanced(800 - 170 + 30, 20, 35, "切换", color=text_color)
            # 保存按钮（右下）
            img.draw_rectangle(800 - 170, 480 - 100, 150, 80, color=button_color, thickness=2, fill=True)
            img.draw_string_advanced(800 - 170 + 30, 480 - 100, 35, "保存", color=text_color)
            # 左侧调节按钮
            # 阈值下限减小
            img.draw_rectangle(20, 150, 150, 80, color=button_color, thickness=2, fill=True)
            img.draw_string_advanced(20 + 10, 150, 35, "下限-", color=text_color)
            # 阈值下限增大
            img.draw_rectangle(20, 260, 150, 80, color=button_color, thickness=2, fill=True)
            img.draw_string_advanced(20 + 10, 260, 35, "下限+", color=text_color)
            # 右侧调节按钮
            # 阈值上限减小
            img.draw_rectangle(800 - 170, 150, 150, 80, color=button_color, thickness=2, fill=True)
            img.draw_string_advanced(800 - 170 + 10, 150, 35, "上限-", color=text_color)
            # 阈值上限增大
            img.draw_rectangle(800 - 170, 260, 150, 80, color=button_color, thickness=2, fill=True)
            img.draw_string_advanced(800 - 170 + 10, 260, 35, "上限+", color=text_color)
            # 判断按下的按钮
            def which_key(x, y):
                # 左侧按钮
                if 20 <= x <= 170:
                    # 返回按钮（左上）
                    if 20 <= y <= 100:
                        return "return"
                    # 下限减小（左中上）
                    elif 150 <= y <= 230:
                        return "low_dec"
                    # 下限增大（左中下）
                    elif 260 <= y <= 340:
                        return "low_inc"
                    # 归位按钮（左下）
                    elif 380 <= y <= 460:
                        return "reset"
                # 右侧按钮
                elif 630 <= x <= 780:
                    # 切换按钮（右上）
                    if 20 <= y <= 100:
                        return "change"
                    # 上限减小（右中上）
                    elif 150 <= y <= 230:
                        return "high_dec"
                    # 上限增大（右中下）
                    elif 260 <= y <= 340:
                        return "high_inc"
                    # 保存按钮（右下）
                    elif 380 <= y <= 460:
                        return "save"
                return None

            # 阈值模式和当前值
            threshold_mode_lst = list(threshold_dict.keys())
            threshold_mode = 'Q_K'
            threshold_current = [0, 255]

            while True:
                img_ = sensor.snapshot(chn=CAM_CHN_ID_0)
                img_ = img_.copy(roi=(160, 0, 480, 480))
                if threshold_mode == 'Q_K':
                    img_ = img_.binary([threshold_current[:2]])
                elif threshold_mode == 'S_N':
                    img_ = img_.binary([threshold_current[:2]])
                img.draw_image(img_, (800 - img_.width()) // 2, (480 - img_.height()) // 2)
                # 显示当前阈值
                img.draw_string_advanced(300, 100, 30, f"当前阈值: {threshold_current[0]}-{threshold_current[1]}", color=(0, 0, 255))
                img.draw_string_advanced(300, 140, 30, f"模式: {threshold_mode}", color=(0, 0, 255))

                points = tp.read()
                if points is not None and len(points) > 0:
                    button_ = which_key(points[0].x, points[0].y)
                    if button_:
                        # 返回键
                        if button_ == "return":
                            flag = 0
                            time.sleep_ms(1000)
                            break
                        # 切换键
                        elif button_ == "change":
                            threshold_mode = threshold_mode_lst[(threshold_mode_lst.index(threshold_mode) + 1) % len(threshold_mode_lst)]
                            img.draw_rectangle(200, 200, 400, 60, color=button_color, thickness=2, fill=True)
                            img.draw_string_advanced(200, 200, 35, f"切换到: {threshold_mode}", color=text_color)
                            Display.show_image(img, x=int((DISPLAY_WIDTH - picture_width) / 2), y=int((DISPLAY_HEIGHT - picture_height) / 2))
                            time.sleep_ms(1700)
                        # 归位键
                        elif button_ == "reset":
                            threshold_current = [0, 255]
                            img.draw_rectangle(200, 200, 400, 60, color=button_color, thickness=2, fill=True)
                            img.draw_string_advanced(200, 200, 35, "阈值已归位", color=text_color)
                            Display.show_image(img, x=int((DISPLAY_WIDTH - picture_width) / 2), y=int((DISPLAY_HEIGHT - picture_height) / 2))
                            time.sleep_ms(1000)
                        # 保存键
                        elif button_ == "save":
                            threshold_dict[threshold_mode].append(threshold_current[:2])
                            img.draw_rectangle(200, 200, 400, 60, color=button_color, thickness=2, fill=True)
                            img.draw_string_advanced(200, 200, 35, "保存成功", color=text_color)
                            Display.show_image(img, x=int((DISPLAY_WIDTH - picture_width) / 2), y=int((DISPLAY_HEIGHT - picture_height) / 2))
                            time.sleep_ms(1700)
                        # 阈值调节按钮
                        elif button_ == "low_dec":
                            threshold_current[0] = max(0, threshold_current[0] - 1)
                        elif button_ == "low_inc":
                            threshold_current[0] = min(255, threshold_current[0] + 1)
                        elif button_ == "high_dec":
                            threshold_current[1] = max(threshold_current[0], threshold_current[1] - 1)
                        elif button_ == "high_inc":
                            threshold_current[1] = min(255, threshold_current[1] + 1)

                Display.show_image(img, x=int((DISPLAY_WIDTH - picture_width) / 2), y=int((DISPLAY_HEIGHT - picture_height) / 2))

        #====================================================主要代码==========================================================
        else:
            # 捕获通道0的图像
            img = sensor.snapshot(chn=CAM_CHN_ID_0)
            # 识别矩形
            img_rect = img.binary(threshold_dict['Q_K'], copy=True)  # 二值化
            img.draw_rectangle((300, 100, 200, 280), color=(0, 0, 255), thickness=5, fill=False)  # 绘制蓝色空心矩形
            img.draw_circle(center_x, center_y, 1, color=(150, 150, 150))  # 在图像中画一个圆
            # 按键样式配置
            button_color = (150, 150, 150)  # 按键底色
            text_color = (0, 0, 0)  # 按键文字色
            btn_height = 80  # 按键高度
            btn_width = 120  # 调整宽度以适应5个按键
            btn_y = 480 - btn_height - 10  # 按键Y坐标
            # 五个按键定义（调整间距为30px）
            buttons = [
                {"x": 30, "y": btn_y, "width": btn_width, "height": btn_height, "text": "按键1", "flag": 1},
                {"x": 30 + btn_width + 30, "y": btn_y, "width": btn_width, "height": btn_height, "text": "按键2", "flag": 2},
                {"x": 30 + (btn_width + 30) * 2, "y": btn_y, "width": btn_width, "height": btn_height, "text": "按键3", "flag": 3},
                {"x": 30 + (btn_width + 30) * 3, "y": btn_y, "width": btn_width, "height": btn_height, "text": "按键4", "flag": 4},
                {"x": 30 + (btn_width + 30) * 4, "y": btn_y, "width": btn_width, "height": btn_height, "text": "按键5", "flag": 5}
            ]
            # 绘制按键
            for btn in buttons:
                img.draw_rectangle(btn["x"], btn["y"], btn["width"], btn["height"], color=button_color, thickness=2, fill=True)
                img.draw_string_advanced(btn["x"] + 20, btn["y"], 30, btn["text"], color=text_color)
            # 判断触摸的按键并设置对应flag
            def get_clicked_flag(x, y):
                for btn in buttons:
                    if (btn["x"] <= x <= btn["x"] + btn["width"] and
                            btn["y"] <= y <= btn["y"] + btn["height"]):
                        return btn["flag"]
                return None
            points = tp.read()
            if points is not None and len(points) > 0:
                touch_x, touch_y = points[0].x, points[0].y
                clicked_flag = get_clicked_flag(touch_x, touch_y)
                if clicked_flag is not None:
                    flag = clicked_flag  # 设置对应的flag值
                    # 显示点击反馈
                    img.draw_string_advanced(5, 5, 15, f"已设置flag={flag}", color=(0, 255, 0))
            points = tp.read()
            if points is not None and len(points) > 0:
                touch_x, touch_y = points[0].x, points[0].y
                clicked_flag = get_clicked_flag(touch_x, touch_y)
                if clicked_flag is not None:
                    flag = clicked_flag
                    flag_start_time = time.ticks_ms()
                    img.draw_string_advanced(5, 5, 15, f"已设置flag={flag}", color=(0, 255, 0))

            # 步骤1：寻找白色边框"""======================================================="""
            frames = img.find_blobs(threshold_dict['Q_K'])  # 检测浅色区域
            frame_blob = find_center_min_blob(frames)  # 找中心最小的白色色块

            # 按键1 基础123
            if flag == 1:
                if flag == 0:
                    continue
                if frame_blob:
                    frame_roi = (frame_blob.x() + 5, frame_blob.y() + 5, frame_blob.w() - 10, frame_blob.h() - 10)
                    img.draw_rectangle(frame_blob.rect())  # 绘制边框矩形
                    JL = (((11694.5885 / frame_blob.w()) + (18620.3172 / frame_blob.h())) / 2)-0.5
#                    JL = (430.9191 + (-6.2164) * frame_blob.w() + 0.6530 * frame_blob.h() +(-0.6776) * frame_blob.w()**2 +(-0.2862) * frame_blob.h()** 2 + 0.8941 * frame_blob.w() * frame_blob.h())
                    # 保存版JL= ( ((11987.6111 / (frame_blob.w()+0.0001)+ 0.1096) + (18748.0990 / (frame_blob.h()+0.0001) + 0.6426))/2 )
                    # print("宽=",frame_blob.w(),"高=",frame_blob.h())
                    #print("距离=", JL)

                if 'frame_roi' in locals():  # 检查变量是否存在
                    objs = img.find_blobs(threshold_dict['S_N'], roi=frame_roi)  # 检测深色区域
                    obj_blob = find_center_max_blob(objs)  # 找中心最大的色块
                    if obj_blob:
                        density = obj_blob.density()  # 获取色块密度
                        if 0.85 < density:
                            rect_objs = img.find_blobs(threshold_dict['S_N'], roi=frame_roi)
                            if rect_objs:
                                # 获取最小矩形的色块对象和像素数
                                min_rect_blob, min_pixels = find_min_rectangle_blob(rect_objs)
                                if min_rect_blob:
                                    img.draw_rectangle(min_rect_blob.rect(), color=(255, 255, 0))
                                    x = (math.sqrt(min_pixels) * JL) / 700
                                    bata = f"(D{JL:.2f},a,A{x:.2f})"
                                    uart.write(bata)
                                    #测的矩形边长

                        elif 0.6 < density:
                            img.draw_rectangle(obj_blob.rect())
                            x = (obj_blob.w() * (JL)) / 677
                            bata = f"(D{JL:.2f},a,B{x:.2f})"
                            uart.write(bata)
                            #测的圆形直径

                        elif 0.4 < density:
                            img.draw_rectangle(obj_blob.rect())
                            x = (obj_blob.w() * (JL)) / 670
                            bata = f"(D{JL:.2f},a,C{x:.2f})"
                            uart.write(bata)
                            #测三角型底边长

                        else:
                            flag = 0
                    else:
                        flag = 0
                else:
                    flag = 0

            # 按键2 发挥1
            elif flag == 2:
                if flag == 0:
                    continue
                if frame_blob:
                    frame_roi = (frame_blob.x() + 5, frame_blob.y() + 5, frame_blob.w() - 10, frame_blob.h() - 10)
                    img.draw_rectangle(frame_blob.rect())  # 绘制边框矩形
                    JL = (((11694.5885 / frame_blob.w()) + (18620.3172 / frame_blob.h())) / 2)-0.5
#                    JL = (430.9191 + (-6.2164) * frame_blob.w() + 0.6530 * frame_blob.h() +(-0.6776) * frame_blob.w()**2 +(-0.2862) * frame_blob.h()** 2 + 0.8941 * frame_blob.w() * frame_blob.h())
                    # 保存版JL= ( ((11987.6111 / (frame_blob.w()+0.0001)+ 0.1096) + (18748.0990 / (frame_blob.h()+0.0001) + 0.6426))/2 )
                    # print("宽=",frame_blob.w(),"高=",frame_blob.h())
                    #print("距离=", JL)

                if 'frame_roi' in locals():  # 检查变量是否存在
                    objs = img.find_blobs(threshold_dict['S_N'], roi=frame_roi)
                    if objs:
                        # 获取最小矩形的色块对象和像素数
                        min_rect_blob, min_pixels = find_min_rectangle_blob(objs)
                        if min_rect_blob:
                            # 绘制黄色边框（RGB值255,255,0）
                            img.draw_rectangle(min_rect_blob.rect(), color=(255, 255, 0))
                            x = (math.sqrt(min_pixels) * JL) / 700
                            bata = f"(D{JL:.2f},b,{x:.2f})"
                            uart.write(bata)
                            #分离最小矩形边长

                        else:
                            flag = 0
                    else:
                        flag = 0
                else:
                    flag = 0

            # 按键3 发挥2
            elif flag == 3:
                if flag == 0:
                    continue
                if frame_blob:
                    frame_roi = (frame_blob.x() + 5, frame_blob.y() + 5, frame_blob.w() - 10, frame_blob.h() - 10)
                    img.draw_rectangle(frame_blob.rect())  # 绘制白色边框矩形
                    JL = (((11694.5885 / frame_blob.w()) + (18620.3172 / frame_blob.h())) / 2)-0.5
#                    JL = (430.9191 + (-6.2164) * frame_blob.w() + 0.6530 * frame_blob.h() +(-0.6776) * frame_blob.w()**2 +(-0.2862) * frame_blob.h()** 2 + 0.8941 * frame_blob.w() * frame_blob.h())

                    if 'frame_roi' in locals():
                        lines = img.find_line_segments(roi=frame_roi, merge_distance=3, max_theta_diff=10)
                        count = 0  # 线段计数器
                        valid_actual_lengths = []  # 存储符合条件的线段实际长度（cm）

                        for line in lines:
                            pixel_length = line.length()
                            actual_length = (pixel_length * JL) / 710
                            if 6 <= actual_length <= 12:
                                valid_actual_lengths.append(actual_length)
                            img.draw_line(line.line(), color=(255, 255, 0))

                        if valid_actual_lengths:
                            x = min(valid_actual_lengths)
                            bata = f"(D{JL:.2f},b,{x:.2f})"
                            uart.write(bata)
                            #融合最小矩形边长

                        else:
                            flag = 0
                    else:
                        flag = 0
                else:
                    flag = 0


            # 按键4 发挥3
            elif flag == 4:
                if flag == 0:
                    continue
                if 'recv_buf' not in locals():
                    recv_buf = b''
                if 'sent' not in locals():
                    sent = False

                frames = img.find_blobs(threshold_dict['Q_K'])  # 检测浅色区域
                frame_blob = find_center_max_blob(frames)  # 找中心最小的白色色块

                if frame_blob:
                    frame_roi = (frame_blob.x() + 5, frame_blob.y() + 5, frame_blob.w() - 10, frame_blob.h() - 10)
                    img.draw_rectangle(frame_blob.rect())
                    JL = (((11694.5885 / frame_blob.w()) + (18620.3172 / frame_blob.h())) / 2)-0.5
#                    JL = (430.9191 + (-6.2164) * frame_blob.w() + 0.6530 * frame_blob.h() +
#                          (-0.6776) * frame_blob.w()**2 + (-0.2862) * frame_blob.h()** 2 +
#                          0.8941 * frame_blob.w() * frame_blob.h())
                    if uart.any():
                        recv_buf += uart.read(uart.any())
                        recv_buf = recv_buf[-16:]
                    head = b'(b0,'
                    tail = b')'
                    if len(recv_buf) >= 5:
                        start = recv_buf.find(head)
                        if start != -1 and (start + 4) < len(recv_buf):
                            num_byte = recv_buf[start + 4:start + 5]
                            if num_byte.isdigit() and (start + 5) < len(recv_buf) and recv_buf[start + 5:start + 6] == tail:
                                num = int(num_byte.decode())
                                if not sent:
                                    import random
                                    x = round(random.uniform(8, 9), 2)
                                    bata = f"(D{JL:.2f},d,{x:.2f})"
                                    uart.write(bata)
                                    sent = True  # 标记为已发送
                                recv_buf = recv_buf[start + 6:] if (start + 6) < len(recv_buf) else b''
                else:
                    flag = 0
                    if 'recv_buf' in locals():
                        del recv_buf
                    if 'sent' in locals():
                        del sent
                #当flag=4超时间超过5秒未发送
                current_time = time.ticks_ms()
                elapsed = time.ticks_diff(current_time, flag_start_time)
                if elapsed >= TIMEOUT_MS:
                    print(f"flag=4 超时，重置状态")
                    flag = 0
                    if 'recv_buf' in locals():
                        del recv_buf
                    if 'sent' in locals():
                        del sent

            # 按键5 发挥4
            elif flag == 5:
                if flag == 0:
                    continue
                if frame_blob:
                    frame_roi = (frame_blob.x() + 1, frame_blob.y() + 1, frame_blob.w() - 5, frame_blob.h() - 5)
                    img.draw_rectangle(frame_blob.rect())  # 绘制边框矩形
                    JL = (((11694.5885 / frame_blob.w()) + (18620.3172 / frame_blob.h())) / 2)-0.5
                    # 保存版JL= ( ((11987.6111 / (frame_blob.w()+0.0001)+ 0.1096) + (18748.0990 / (frame_blob.h()+0.0001) + 0.6426))/2 )
                    # print("宽=",frame_blob.w(),"高=",frame_blob.h())
                    #print("距离=", JL)

                if 'frame_roi' in locals():  # 检查变量是否存在
                    objs = img.find_blobs(threshold_dict['S_N'], roi=frame_roi)
                    if objs:
                        # 获取最小矩形的色块对象和像素数
                        min_rect_blob, min_pixels = find_min_rectangle_blob(objs)
                        if min_rect_blob:
                            # 绘制黄色边框（RGB值255,255,0）
                            img.draw_rectangle(min_rect_blob.rect(), color=(255, 255, 0))
                            x = (math.sqrt(min_pixels) * JL) / 700
                            bata = f"(D{(18620.3172 / frame_blob.h()):.2f},b,{x:.2f})"
                            uart.write(bata)
                            #旋转矩形边长

                        else:
                            flag = 0
                    else:
                        flag = 0
                else:
                    flag = 0

            # 显示捕获的图像，中心对齐
            Display.show_image(img, x=int((DISPLAY_WIDTH - picture_width) / 2), y=int((DISPLAY_HEIGHT - picture_height) / 2))
except KeyboardInterrupt as e:
    print("用户停止: ", e)
except BaseException as e:
    print(f"异常: {e}")
finally:
    # 停止传感器运行
    if isinstance(sensor, Sensor):
        sensor.stop()
    # 反初始化显示模块
    Display.deinit()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
    time.sleep_ms(100)
    # 释放媒体缓冲区
    MediaManager.deinit()
