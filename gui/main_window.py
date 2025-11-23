import sys
import vlc
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel, 
                             QLineEdit, QPushButton, QSplitter, QFrame, QSlider,
                             QMessageBox, QInputDialog, QSizePolicy, QStackedLayout, QStyle)
from PyQt6.QtCore import Qt, QTimer, QUrl, QSize, QEvent
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QDesktopServices
from PyQt6.QtSvg import QSvgRenderer

from core.webdav_client import WebDAVClient
from core.search_client import SearchClient
from core.sorter import SmartSorter
from core.config import Config
import gui.icons as icons
import os

# 支持的视频格式
VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', 
    '.m4v', '.mpg', '.mpeg', '.rmvb', '.ts', '.m2ts', '.vob', '.m3u8'
}

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小雅 Alist 播放器")
        self.resize(1200, 800)
        
        self.config = Config()
        
        # 加载配置
        self.webdav_url = self.config.get("webdav_url", "http://118.122.130.22:5678/dav")
        self.username = self.config.get("username", "guest")
        self.password = self.config.get("password", "guest_Api789")
        self.skip_intro = self.config.get("skip_intro", 0)
        self.skip_outro = self.config.get("skip_outro", 0)
        
        self.skip_intro = self.config.get("skip_intro", 0)
        self.skip_outro = self.config.get("skip_outro", 0)
        
        self.client = None
        self.search_client = SearchClient(self.webdav_url)
        self.current_playlist = []
        self.current_index = -1
        self.duration = 0
        self.is_muted = False
        self.saved_volume = 100
        self.pending_resume_time = None
        
        # 片头片尾跳过标志
        self.intro_skipped = False
        self.outro_skipped = False
        
        # 视频结束标志（用于自动播放下一集）
        self.video_ended = False
        
        # 播放历史恢复标志（防止重复恢复）
        self.history_restored = False
        
        # 长按标志
        self.intro_btn_long_press_active = False
        self.outro_btn_long_press_active = False
        
        # 长按计时器
        self.intro_btn_timer = QTimer(self)
        self.intro_btn_timer.setInterval(1000)
        self.intro_btn_timer.setSingleShot(True)
        
        self.outro_btn_timer = QTimer(self)
        self.outro_btn_timer.setInterval(1000)
        self.outro_btn_timer.setSingleShot(True)
        
        # 初始化UI和VLC
        self.init_ui()
        self.init_vlc()
        
        # 连接计时器信号
        self.intro_btn_timer.timeout.connect(self.reset_intro)
        self.outro_btn_timer.timeout.connect(self.reset_outro)
        
        # 启动时自动连接（但不自动恢复播放历史）
        QTimer.singleShot(100, self.connect_webdav)
        
        # 控制栏自动隐藏计时器
        self.hide_controls_timer = QTimer(self)
        self.hide_controls_timer.setInterval(5000)
        self.hide_controls_timer.timeout.connect(self.hide_controls)
        
        # OSD 计时器
        self.osd_timer = QTimer(self)
        self.osd_timer.setInterval(2000)
        self.osd_timer.setSingleShot(True)
        self.osd_timer.timeout.connect(self.clear_osd)
        
        # 鼠标跟踪（用于自动隐藏控制栏）
        self.setMouseTracking(True)
        if self.centralWidget() is not None:
            self.centralWidget().setMouseTracking(True)
        self.video_frame.setMouseTracking(True)
        self.video_frame.installEventFilter(self)

    def _create_icon(self, svg_data, color="white"):
        renderer = QSvgRenderer(bytearray(svg_data, encoding='utf-8'))
        pixmap = QPixmap(36, 36)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def init_ui(self):
        # Bilibili 风格样式
        bilibili_btn_style = """
            QPushButton {
                background-color: #1a1a1a;
                color: white;
                border: 1px solid #2e2e2e;
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
            }
            QPushButton:pressed {
                background-color: #00aeec;
                border: 1px solid #00aeec;
            }
        """

        bilibili_slider_style = """
            QSlider::groove:horizontal {
                height: 6px;
                background: #2e2e2e;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #00aeec;
                border-radius: 3px;
            }
            QSlider::add-page:horizontal {
                background: #2e2e2e;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: none;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """

        bilibili_tree_style = """
            QTreeWidget {
                background-color: #0f0f0f;
                color: #bbbbbb;
                border: none;
            }
            QTreeWidget::item {
                padding: 6px;
            }
            QTreeWidget::item:selected {
                background-color: #00aeec;
                color: black;
            }
        """

        bilibili_topbar_style = """
            background-color: rgba(30, 30, 30, 200);
            border-bottom: 1px solid rgba(255, 255, 255, 30);
        """

        bilibili_panel_style = "background-color: black;"
        
        # 主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("background-color: #000000; color: white;")
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter container
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #333; }")
        self.splitter.setChildrenCollapsible(False)
        main_layout.addWidget(self.splitter)

        # -------------------- Left Panel: File Browser --------------------
        self.left_panel = QWidget()
        self.left_panel.setStyleSheet("background-color: #0f0f0f; border-right: 1px solid #222;")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(8)

        # Address Bar
        addr_layout = QHBoxLayout()
        self.url_input = QLineEdit(self.webdav_url)
        self.url_input.setStyleSheet("background-color: #1a1a1a; color: white; border: 1px solid #333; padding: 6px; border-radius:6px;")
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setStyleSheet(bilibili_btn_style)
        self.connect_btn.setFixedWidth(60)
        self.connect_btn.clicked.connect(self.connect_webdav)
        addr_layout.addWidget(self.url_input)
        addr_layout.addWidget(self.connect_btn)
        left_layout.addLayout(addr_layout)

        # 搜索区域
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索小雅资源...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a1a;
                color: white;
                border: 1px solid #333;
                padding: 6px;
                border-radius: 6px;
            }
            QLineEdit:focus {
                border: 1px solid #00aeec;
            }
        """)
        self.search_input.returnPressed.connect(self.perform_search)
        
        search_btn = QPushButton("搜索")
        search_btn.setStyleSheet(bilibili_btn_style)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setFixedWidth(60)
        search_btn.clicked.connect(self.perform_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        left_layout.addLayout(search_layout)

        # Tree View
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("文件列表")
        self.tree.setHeaderHidden(True) # 隐藏表头
        self.tree.setStyleSheet(bilibili_tree_style)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.itemExpanded.connect(self.on_item_expanded)
        left_layout.addWidget(self.tree)

        # GitHub链接按钮
        self.github_btn = QPushButton("⭐ GitHub")
        self.github_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #00aeec;
                border: 1px solid #00aeec;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #00aeec;
                color: white;
            }
        """)
        self.github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.github_btn.clicked.connect(self.open_github)
        left_layout.addWidget(self.github_btn)

        self.left_panel.setMinimumWidth(250)
        self.left_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.splitter.addWidget(self.left_panel)

        # 右侧面板：播放器
        right_panel = QWidget()
        right_panel.setStyleSheet(bilibili_panel_style)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 顶部标题栏
        self.top_bar = QWidget()
        self.top_bar.setStyleSheet(bilibili_topbar_style)
        self.top_bar.setFixedHeight(48)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(15, 0, 15, 0)
        self.title_label = QLabel("")
        self.title_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        top_layout.addWidget(self.title_label)
        right_layout.addWidget(self.top_bar)

        # Video Frame
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout.addWidget(self.video_frame, stretch=1)

        # Controls Container
        self.controls_container = QWidget()
        self.controls_container.setStyleSheet("background-color: rgba(20,20,20,200); border-radius: 16px;")
        self.controls_container.setFixedHeight(100)
        controls_layout = QVBoxLayout(self.controls_container)
        controls_layout.setContentsMargins(10, 6, 10, 6)
        controls_layout.setSpacing(6)

        # Progress Bar layout
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setStyleSheet("color: #cccccc; background: transparent;")
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setStyleSheet("color: #cccccc; background: transparent;")

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setStyleSheet(bilibili_slider_style)
        # 使用 valueChanged 信号，支持点击和拖动
        self.seek_slider.valueChanged.connect(self.on_seek_slider_changed)

        progress_layout.addWidget(self.current_time_label)
        progress_layout.addWidget(self.seek_slider)
        progress_layout.addWidget(self.total_time_label)
        controls_layout.addLayout(progress_layout)

        # Buttons layout
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(12)

        # round small control button style
        round_btn_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 22px;
                min-width: 44px;
                min-height: 44px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,30); }
            QPushButton:pressed { background-color: rgba(255,255,255,50); }
        """

        # 确保按钮存在
        for attr in ("prev_btn", "play_btn", "stop_btn", "next_btn", "vol_btn", "fullscreen_btn"):
            if not hasattr(self, attr):
                setattr(self, attr, QPushButton())
            getattr(self, attr).setStyleSheet(round_btn_style)

        # 设置图标和事件
        self.prev_btn.setIcon(self._create_icon(icons.PREV_ICON))
        self.prev_btn.clicked.connect(self.play_prev)
        self.play_btn.setIcon(self._create_icon(icons.PLAY_ICON))
        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn.setIcon(self._create_icon(icons.STOP_ICON))
        self.stop_btn.clicked.connect(self.stop_playback)
        self.next_btn.setIcon(self._create_icon(icons.NEXT_ICON))
        self.next_btn.clicked.connect(self.play_next)
        self.vol_btn.setIcon(self._create_icon(icons.VOLUME_ICON))
        self.vol_btn.clicked.connect(self.toggle_mute)
        self.fullscreen_btn.setIcon(self._create_icon(icons.FULLSCREEN_ICON))
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        # 片头片尾按钮
        if not hasattr(self, "set_intro_btn"):
            self.set_intro_btn = QPushButton("设为片头")
        if not hasattr(self, "set_outro_btn"):
            self.set_outro_btn = QPushButton("设为片尾")

        io_btn_style = bilibili_btn_style
        self.set_intro_btn.setStyleSheet(io_btn_style)
        self.set_outro_btn.setStyleSheet(io_btn_style)

        # 重新连接长按信号
        try:
            # avoid duplicate connections by disconnecting then reconnecting
            try:
                self.set_intro_btn.pressed.disconnect()
            except Exception:
                pass
            try:
                self.set_intro_btn.released.disconnect()
            except Exception:
                pass
        except Exception:
            pass
        self.set_intro_btn.pressed.connect(self.on_intro_btn_pressed)
        self.set_intro_btn.released.connect(self.on_intro_btn_released)

        try:
            try:
                self.set_outro_btn.pressed.disconnect()
            except Exception:
                pass
            try:
                self.set_outro_btn.released.disconnect()
            except Exception:
                pass
        except Exception:
            pass
        self.set_outro_btn.pressed.connect(self.on_outro_btn_pressed)
        self.set_outro_btn.released.connect(self.on_outro_btn_released)

        # 更新按钮文本
        if self.skip_intro > 0:
            self.set_intro_btn.setText(f"片头: {self.skip_intro}s")
        if self.skip_outro > 0:
            self.set_outro_btn.setText(f"片尾: {self.skip_outro}s")

        # 音量滑块
        if not hasattr(self, "vol_slider"):
            self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.setFixedWidth(100)
        self.vol_slider.setStyleSheet(bilibili_slider_style)
        # reconnect signal safely
        try:
            self.vol_slider.valueChanged.disconnect()
        except Exception:
            pass
        # 使用 valueChanged 信号，支持点击和拖动
        self.vol_slider.valueChanged.connect(self.set_volume)

        # Add widgets to btns_layout in the same order as original
        btns_layout.addWidget(self.prev_btn)
        btns_layout.addWidget(self.play_btn)
        btns_layout.addWidget(self.stop_btn)
        btns_layout.addWidget(self.next_btn)
        btns_layout.addStretch()
        btns_layout.addWidget(self.set_intro_btn)
        btns_layout.addWidget(self.set_outro_btn)
        btns_layout.addStretch()
        btns_layout.addWidget(self.vol_btn)
        btns_layout.addWidget(self.vol_slider)
        btns_layout.addWidget(self.fullscreen_btn)

        controls_layout.addLayout(btns_layout)
        right_layout.addWidget(self.controls_container)

        # 将右侧面板添加到Splitter
        self.splitter.addWidget(right_panel)
        # 设置Splitter初始比例
        self.splitter.setSizes([300, 900])
        # 设置右侧拉伸因子
        self.splitter.setStretchFactor(1, 1)

        # UI更新计时器
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()

    def init_vlc(self):
        # VLC 初始化参数：禁用硬件加速、禁用VLC鼠标键盘事件
        vlc_args = [
            "--avcodec-hw=none",
            "--no-mouse-events",
            "--no-keyboard-events",
            "--no-osd",
            "--no-video-title-show",
        ]
        
        self.instance = vlc.Instance(" ".join(vlc_args))
        self.player = self.instance.media_player_new()
        
        # 禁用VLC鼠标键盘输入
        self.player.video_set_mouse_input(False)
        self.player.video_set_key_input(False)
        
        # 绑定到窗口
        if sys.platform.startswith('linux'):
            self.player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":
            self.player.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":
            self.player.set_nsobject(int(self.video_frame.winId()))

    def on_intro_btn_pressed(self):
        """片头按钮按下"""
        self.intro_btn_long_press_active = False
        self.intro_btn_timer.start()

    def on_intro_btn_released(self):
        """片头按钮释放"""
        self.intro_btn_timer.stop()
        
        if not self.intro_btn_long_press_active:
            self.set_intro()
        
        self.intro_btn_long_press_active = False

    def on_outro_btn_pressed(self):
        """片尾按钮按下"""
        self.outro_btn_long_press_active = False
        self.outro_btn_timer.start()

    def on_outro_btn_released(self):
        """片尾按钮释放"""
        self.outro_btn_timer.stop()
        
        if not self.outro_btn_long_press_active:
            self.set_outro()
        
        self.outro_btn_long_press_active = False

    def set_intro(self):
        """设置片头时间"""
        time = self.player.get_time()
        if time > 0:
            self.skip_intro = time // 1000
            self.config.set("skip_intro", self.skip_intro)
            self.config.save()
            self.set_intro_btn.setText(f"片头: {self.skip_intro}s")
            self.show_osd(f"设置片头: {self.skip_intro}s")
            
    def reset_intro(self):
        """长按片头按钮时重置"""
        self.intro_btn_long_press_active = True  # 标记为长按，阻止 released 中的设置操作
        self.skip_intro = 0
        self.config.set("skip_intro", 0)
        self.config.save()
        self.set_intro_btn.setText("设为片头")
        self.show_osd("重置片头")

    def set_outro(self):
        """设置片尾时间（短按触发）"""
        length = self.player.get_length()
        time = self.player.get_time()
        if length > 0 and time > 0:
            self.skip_outro = (length - time) // 1000
            self.config.set("skip_outro", self.skip_outro)
            self.config.save()
            self.set_outro_btn.setText(f"片尾: {self.skip_outro}s")
            self.show_osd(f"设置片尾: {self.skip_outro}s")

    def reset_outro(self):
        """长按片尾按钮时重置"""
        self.outro_btn_long_press_active = True  # 标记为长按，阻止 released 中的设置操作
        self.skip_outro = 0
        self.config.set("skip_outro", 0)
        self.config.save()
        self.set_outro_btn.setText("设为片尾")
        self.show_osd("重置片尾")
    
    def load_dir(self, path, parent_item=None):
        """加载目录"""
        if not self.client:
            return
            
        if parent_item is None:
            self.tree.clear()
            parent_item = self.tree.invisibleRootItem()
        else:
            # Remove dummy item
            parent_item.takeChildren()
            
        items = self.client.list_files(path)
        
        # Sort items: Directories first, then Files (Smart Sorted)
        dirs = [i for i in items if i['type'] == 'directory']
        files = [i for i in items if i['type'] != 'directory']
        
        # Filter video files
        files = [f for f in files if os.path.splitext(f['name'])[1].lower() in VIDEO_EXTENSIONS]
        
        # Sort directories alphabetically
        dirs.sort(key=lambda x: x['name'])
        
        # Smart sort files
        files = SmartSorter.sort_files(files)
        
        for item in dirs:
            # Display only the directory name, not the full path
            display_name = os.path.basename(item['name'].rstrip('/'))
            tree_item = QTreeWidgetItem(parent_item, [display_name])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, item)
            # Add dummy child to make it expandable
            QTreeWidgetItem(tree_item, ["加载中..."])
            
        for item in files:
            tree_item = QTreeWidgetItem(parent_item, [os.path.basename(item['name'])])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, item)

    def connect_webdav(self):
        """连接WebDAV服务器"""
        url = self.url_input.text()
        if not url.startswith("http"):
            url = "http://" + url
            
        self.webdav_url = url
        self.config.set("webdav_url", self.webdav_url)
        
        try:
            self.client = WebDAVClient(self.webdav_url, self.username, self.password)
            self.client.list_files("/")
            self.load_dir("/")
            self.config.save()
            self.show_osd("连接成功")
            
            # 连接成功，但不自动恢复播放历史（改为用户点击播放时才恢复）
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))
            self.show_osd("连接失败")

    def on_item_expanded(self, item):
        if item.childCount() == 1 and item.child(0).text(0) == "加载中...":
            data = item.data(0, Qt.ItemDataRole.UserRole)
            path = data['name']
            self.load_dir(path, item)

    def on_item_double_clicked(self, item, column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data['type'] == 'directory':
            if item.isExpanded():
                item.setExpanded(False)
            else:
                item.setExpanded(True)
        else:
            parent = item.parent()
            if parent:
                self.current_playlist = []
                for i in range(parent.childCount()):
                    child = parent.child(i)
                    child_data = child.data(0, Qt.ItemDataRole.UserRole)
                    if child_data['type'] != 'directory':
                        self.current_playlist.append(child_data)
            else:
                self.current_playlist = [data]
                
            try:
                self.current_index = self.current_playlist.index(data)
            except ValueError:
                self.current_index = 0
                self.current_playlist = [data]
                
            self.play_video(data)

    def play_video(self, file_data, resume_time=None):
        """播放视频
        
        Args:
            file_data: 文件数据
            resume_time: 恢复播放时间（毫秒）
        """
        path = file_data['name']
        url = self.client.get_stream_url(path)
        
        media = self.instance.media_new(url)
        self.player.set_media(media)
        self.player.play()
        
        self.title_label.setText(os.path.basename(path))
        self.play_btn.setIcon(self._create_icon(icons.PAUSE_ICON))
        
        self.config.set("last_played_path", path)
        self.config.save()
        
        # 重置片头片尾跳过标志和视频结束标志
        self.intro_skipped = False
        self.outro_skipped = False
        self.video_ended = False
        
        # 设置恢复时间
        if resume_time is not None and resume_time > 0:
            self.pending_resume_time = resume_time
            # 如果恢复时间超过片头时间，标记片头已跳过
            if self.skip_intro > 0 and resume_time >= self.skip_intro * 1000:
                self.intro_skipped = True
            print(f"[DEBUG] Set pending resume time: {resume_time}ms")
        
        self.show_controls()

    def toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
            self.play_btn.setIcon(self._create_icon(icons.PLAY_ICON))
            self.show_osd("暂停")
        else:
            # 如果当前没有播放内容，且未恢复过播放历史，则先恢复
            if not self.history_restored and len(self.current_playlist) == 0 and self.client:
                self.restore_playback_history()
                return  # restore_playback_history 会自动开始播放
            
            self.player.play()
            self.play_btn.setIcon(self._create_icon(icons.PAUSE_ICON))
            self.show_osd("播放")
            
    def stop_playback(self):
        """停止播放"""
        self.player.stop()
        self.play_btn.setIcon(self._create_icon(icons.PLAY_ICON))
        self.show_osd("停止")
            
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.left_panel.show()
            self.top_bar.setVisible(True)
            self.fullscreen_btn.setIcon(self._create_icon(icons.FULLSCREEN_ICON))
        else:
            self.showFullScreen()
            self.left_panel.hide()
            self.fullscreen_btn.setIcon(self._create_icon(icons.FULLSCREEN_EXIT_ICON))
            
    def toggle_mute(self):
        """
        切换静音状态
        使用 audio_set_volume(0) 而不是 audio_set_mute，
        因为 audio_set_mute 会与硬件加速产生冲突。
        """
        if self.is_muted:
            # 取消静音：恢复之前保存的音量
            self.player.audio_set_volume(self.saved_volume)
            self.vol_slider.setValue(self.saved_volume)
            self.vol_btn.setIcon(self._create_icon(icons.VOLUME_ICON))
            self.show_osd("取消静音")
            self.is_muted = False
        else:
            # 静音：保存当前音量后设为 0
            self.saved_volume = self.player.audio_get_volume()
            self.player.audio_set_volume(0)
            self.vol_slider.setValue(0)
            self.vol_btn.setIcon(self._create_icon(icons.MUTE_ICON))
            self.show_osd("静音")
            self.is_muted = True

    def set_volume(self, volume):
        """设置音量，不显示 OSD（避免频繁调用导致解码器冲突）"""
        self.player.audio_set_volume(volume)
        # 如果正在静音状态下调整音量，自动取消静音
        if self.is_muted and volume > 0:
            self.is_muted = False
            self.vol_btn.setIcon(self._create_icon(icons.VOLUME_ICON))
        
    def set_position(self, position):
        """用户手动拖动进度条时调用"""
        if self.duration > 0:
            pos = position / 1000.0
            self.player.set_position(pos)
    
    def on_seek_slider_changed(self, position):
        """进度条值改变时调用（点击或拖动）"""
        # 因为update_ui使用了blockSignals，所以这里只会在用户操作时触发
        self.set_position(position)
            
    def play_prev(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.play_video(self.current_playlist[self.current_index])
            self.show_osd("上一集")
            
    def play_next(self):
        if self.current_index < len(self.current_playlist) - 1:
            self.current_index += 1
            self.play_video(self.current_playlist[self.current_index])
            self.show_osd("下一集")
            
    def show_controls(self):
        self.controls_container.show()
        if self.isFullScreen():
            self.top_bar.show()
        self.hide_controls_timer.start()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        
    def hide_controls(self):
        if self.isFullScreen() and self.player.is_playing():
            self.controls_container.hide()
            self.top_bar.hide()
            self.setCursor(Qt.CursorShape.BlankCursor)

    def update_ui(self):
        if self.player.is_playing():
            length = self.player.get_length()
            time = self.player.get_time()
            
            if length > 0:
                self.duration = length
                # protect divide by zero
                # 更新进度条时阻止信号，避免触发valueChanged
                try:
                    self.seek_slider.blockSignals(True)
                    self.seek_slider.setValue(int(time / length * 1000))
                    self.seek_slider.blockSignals(False)
                except Exception:
                    pass
                
                # 如果有待恢复的时间，且视频已加载，进行跳转
                if self.pending_resume_time is not None:
                    print(f"[DEBUG] Seeking to pending resume time: {self.pending_resume_time}ms, video length: {length}ms")
                    self.player.set_time(int(self.pending_resume_time))
                    self.show_osd(f"恢复播放: {int(self.pending_resume_time/1000)}s")
                    self.pending_resume_time = None  # 清除，避免重复跳转
                
                def format_time(ms):
                    s = ms // 1000
                    m = s // 60
                    s = s % 60
                    h = m // 60
                    m = m % 60
                    if h > 0:
                        return f"{h:02}:{m:02}:{s:02}"
                    return f"{m:02}:{s:02}"
                
                self.current_time_label.setText(format_time(time))
                self.total_time_label.setText(format_time(length))
                
                # 定期保存播放进度（每5秒保存一次，避免频繁写入）
                if int(time / 1000) % 5 == 0:
                    self.config.set("last_played_time", int(time))
                
                # 只在视频刚开始播放时跳过片头（前5秒内），确保用户手动拖回去不会被强制跳转
                if self.skip_intro > 0 and not self.intro_skipped and time < 5000 and time < self.skip_intro * 1000:
                    self.player.set_time(self.skip_intro * 1000)
                    self.intro_skipped = True  # 标记已跳过
                    self.show_osd(f"跳过片头 ({self.skip_intro}s)")
                
                # 只跳过片尾一次
                if self.skip_outro > 0 and not self.outro_skipped and length - time < self.skip_outro * 1000:
                    self.outro_skipped = True  # 先标记，避免重复
                    self.play_next()
                    self.show_osd(f"跳过片尾 ({self.skip_outro}s)")
                
                # 视频播放结束自动播放下一集（不依赖片尾设置）
                if not self.video_ended and length - time < 1000:  # 剩余时间少于1秒
                    self.video_ended = True
                    if self.current_index < len(self.current_playlist) - 1:
                        QTimer.singleShot(500, self.play_next)  # 延迟500ms播放下一集

    def eventFilter(self, source, event):
        """处理视频区域的鼠标事件"""
        if source == self.video_frame:
            event_type = event.type()
            
            if event_type == QEvent.Type.MouseMove:
                # 鼠标移动时显示控制栏
                self.show_controls()
                return False  # 让事件继续传播
                
            elif event_type == QEvent.Type.MouseButtonDblClick:
                # 双击时切换播放/暂停
                print("[DEBUG] Double click detected!")  # 调试信息
                self.toggle_play()
                return True  # 阻止事件继续传播
                
        return super().eventFilter(source, event)
                
    def keyPressEvent(self, event):
        self.show_controls() # Wake up controls on key press
        key = event.key()
        
        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self.toggle_fullscreen()
        elif key == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.toggle_fullscreen()
        elif key == Qt.Key.Key_Space:
            self.toggle_play()
        elif key == Qt.Key.Key_Up:
            vol = self.player.audio_get_volume()
            self.set_volume(min(vol + 5, 100))
            self.vol_slider.setValue(self.player.audio_get_volume())
        elif key == Qt.Key.Key_Down:
            vol = self.player.audio_get_volume()
            self.set_volume(max(vol - 5, 0))
            self.vol_slider.setValue(self.player.audio_get_volume())
        elif key == Qt.Key.Key_Left:
            time = self.player.get_time()
            self.set_position(max(time - 15000, 0))
            self.show_osd("快退 15s")
        elif key == Qt.Key.Key_Right:
            time = self.player.get_time()
            length = self.player.get_length()
            self.set_position(min(time + 15000, length))
            self.show_osd("快进 15s")
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Z:
                self.play_prev()
            elif key == Qt.Key.Key_X:
                self.play_next()
        else:
            super().keyPressEvent(event)
        
    def show_osd(self, text):
        # VLC Marquee
        try:
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Enable, 1)
            self.player.video_set_marquee_string(vlc.VideoMarqueeOption.Text, text)
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Position, 5) # 5 = Top-Left
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Color, 0xFFFFFF) # White
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Size, 48)
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Timeout, 2000)
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Refresh, 1)
        except Exception:
            pass
        self.osd_timer.start()

    def clear_osd(self):
        try:
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Enable, 0)
        except Exception:
            pass

    def navigate_to_file(self, file_path):
        """在文件树中导航到指定文件并选中
        
        Args:
            file_path: 文件的完整路径
        """
        # 分割路径为各个部分
        parts = file_path.strip('/').split('/')
        if not parts:
            return
        
        # 从根开始遍历
        current_item = None
        root = self.tree.invisibleRootItem()
        
        for i, part in enumerate(parts):
            found = False
            parent = current_item if current_item else root
            
            # 遍历当前层级的所有子项
            for j in range(parent.childCount()):
                child = parent.child(j)
                child_data = child.data(0, Qt.ItemDataRole.UserRole)
                
                if child_data:
                    child_name = os.path.basename(child_data['name'].rstrip('/'))
                    if child_name == part:
                        found = True
                        current_item = child
                        
                        # 如果不是最后一个部分（即是目录），展开它
                        if i < len(parts) - 1:
                            if not child.isExpanded():
                                child.setExpanded(True)
                                # 触发加载子项
                                self.on_item_expanded(child)
                        else:
                            # 是文件，选中它
                            self.tree.setCurrentItem(child)
                            self.tree.scrollToItem(child)
                        break
            
            if not found:
                break
    
    def restore_playback_history(self):
        """恢复上次播放的视频和进度"""
        # 防止重复恢复
        if self.history_restored:
            return
        
        self.history_restored = True
        
        last_path = self.config.get("last_played_path")
        last_time = self.config.get("last_played_time", 0)
        
        if not last_path or not self.client:
            return
        
        try:
            # 导航到文件
            self.navigate_to_file(last_path)
            
            # 获取父目录路径
            parent_path = '/'.join(last_path.strip('/').split('/')[:-1])
            if parent_path:
                parent_path = '/' + parent_path
            else:
                parent_path = '/'
            
            # 加载播放列表（父目录的所有视频）
            items = self.client.list_files(parent_path)
            files = [f for f in items if f['type'] != 'directory' and 
                    os.path.splitext(f['name'])[1].lower() in VIDEO_EXTENSIONS]
            files = SmartSorter.sort_files(files)
            
            self.current_playlist = files
            
            # 找到当前文件在播放列表中的索引
            for i, f in enumerate(files):
                if f['name'] == last_path:
                    self.current_index = i
                    # 播放视频并恢复进度
                    self.play_video(f, resume_time=last_time)
                    self.show_osd("已恢复播放历史")
                    break
        except Exception as e:
            print(f"Failed to restore playback history: {e}")
    
    def closeEvent(self, event):
        # 保存最终播放进度
        try:
            if self.player.is_playing():
                time = self.player.get_time()
                self.config.set("last_played_time", int(time))
        except Exception:
            pass
        self.config.save()
        super().closeEvent(event)
    
    def open_github(self):
        """打开GitHub仓库"""
        QDesktopServices.openUrl(QUrl("https://github.com/ymh1146/xiaoyaplayer"))

    def perform_search(self):
        """执行搜索"""
        keyword = self.search_input.text().strip()
        if not keyword:
            return
            
        self.show_osd("正在搜索...")
        # 禁用搜索按钮防止重复点击
        self.search_input.setEnabled(False)
        
        try:
            # 执行搜索
            results = self.search_client.search(keyword)
            
            if not results:
                self.show_osd("未找到相关资源")
                self.search_input.setEnabled(True)
                self.search_input.setFocus()
                return
                
            # 清空树并显示结果
            self.tree.clear()
            self.tree.setHeaderLabel(f"搜索结果: {keyword}")
            
            for path in results:
                item = QTreeWidgetItem(self.tree)
                item.setText(0, path)
                # 使用文件夹图标，因为搜索结果通常是目录
                item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                # 标记为搜索结果
                item.setData(0, Qt.ItemDataRole.UserRole, {"type": "search_result", "path": path})
                
            self.show_osd(f"找到 {len(results)} 个结果")
            
        except Exception as e:
            self.show_osd(f"搜索出错: {str(e)}")
            print(f"[ERROR] Search error: {e}")
            
        finally:
            self.search_input.setEnabled(True)
            self.search_input.setFocus()

    def on_item_double_clicked(self, item, column):
        """双击列表项"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
            
        # 处理搜索结果点击
        if isinstance(data, dict) and data.get("type") == "search_result":
            path = data["path"]
            print(f"[DEBUG] Loading search result path: {path}")
            self.load_dir(path)
            # 恢复树标题
            self.tree.setHeaderLabel("文件列表")
            return
            
        # 原有逻辑：处理文件或目录
        if data['type'] == 'directory':
            self.load_dir(data['name'], item)
        else:
            # 播放视频
            self.current_playlist = []
            # 获取当前目录下的所有视频文件
            parent = item.parent()
            if parent:
                for i in range(parent.childCount()):
                    child = parent.child(i)
                    child_data = child.data(0, Qt.ItemDataRole.UserRole)
                    if child_data['type'] != 'directory' and \
                       os.path.splitext(child_data['name'])[1].lower() in VIDEO_EXTENSIONS:
                        self.current_playlist.append(child_data)
            else:
                # 根目录文件（不太可能，但为了健壮性）
                self.current_playlist.append(data)
            
            # 找到当前文件的索引
            for i, f in enumerate(self.current_playlist):
                if f['name'] == data['name']:
                    self.current_index = i
                    break
            
            self.play_video(data)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    
    # Connect expansion signal (safe to connect; method exists)
    window.tree.itemExpanded.connect(window.on_item_expanded)
    
    window.show()
    sys.exit(app.exec())
