import os
import requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import AsyncImage, Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.utils import platform, get_color_from_hex
from kivy.graphics import Color, RoundedRectangle

# Настройки стиля
ANDROID_ICONS = ["icon1.png", "icon2.png", "icon3.png"]
IOS_BLUE = get_color_from_hex("#007AFF")

class AppRow(BoxLayout):
    def __init__(self, app_data, is_android, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = "90dp"
        self.padding = "10dp"
        self.spacing = "15dp"

        # 1. Логика Иконок
        if is_android:
            # Маскировка под Android (используем твои иконки по очереди)
            idx = kwargs.get('idx', 0) % len(ANDROID_ICONS)
            icon_src = ANDROID_ICONS[idx] if os.path.exists(ANDROID_ICONS[idx]) else "default_android.png"
            self.add_widget(Image(source=icon_src, size_hint_x=None, width="70dp"))
        else:
            # Стиль iOS (загрузка реальной иконки приложения)
            self.add_widget(AsyncImage(source=app_data['icon_url'], size_hint_x=None, width="70dp"))

        # 2. Инфо об приложении
        info = BoxLayout(orientation='vertical')
        info.add_widget(Label(text=app_data['name'], bold=True, halign='left', color=(0,0,0,1) if not is_android else (1,1,1,1)))
        info.add_widget(Label(text=app_data['version'], font_size='12sp', color=(0.5,0.5,0.5,1)))
        self.add_widget(info)

        # 3. Кнопка установки
        btn_text = "INSTALL" if is_android else "GET"
        btn = Button(
            text=btn_text,
            size_hint=(None, None),
            size=("85dp", "35dp"),
            pos_hint={'center_y': .5},
            background_color=IOS_BLUE if not is_android else (0.2, 0.7, 0.2, 1),
            background_normal=''
        )
        btn.bind(on_release=lambda x: self.start_install(app_data))
        self.add_widget(btn)

    def start_install(self, data):
        print(f"Загрузка {data['name']}...")
        # Сюда вставляем твою логику скачивания из первого примера

class ReloadedStoreInstaller(App):
    def build(self):
        self.is_android = (platform == 'android')
        
        # Главный фон
        root = BoxLayout(orientation='vertical')
        with root.canvas.before:
            Color(*(1, 1, 1, 1) if not self.is_android else (0.1, 0.1, 0.1, 1))
            self.bg = RoundedRectangle(pos=(0,0), size=(2000, 2000))

        # Хедер
        header = Label(
            text="Reloaded Store" if not self.is_android else "System Apps",
            size_hint_y=None, height="60dp",
            bold=True, font_size="22sp",
            color=(0,0,0,1) if not self.is_android else (1,1,1,1)
        )
        root.add_widget(header)

        # Список приложений (Scroll)
        scroll = ScrollView()
        self.list_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing="5dp")
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        
        # Данные (в реальности придут с твоего сервера)
        apps_data = [
            {"name": "Home Radio Pro", "version": "2.1", "icon_url": "http://..."},
            {"name": "Artem Maps XR", "version": "1.0", "icon_url": "http://..."},
            {"name": "Internet Archive App", "version": "3.4", "icon_url": "http://..."}
        ]

        for i, app in enumerate(apps_data):
            self.list_layout.add_widget(AppRow(app, self.is_android, idx=i))

        scroll.add_widget(self.list_layout)
        root.add_widget(scroll)
        
        return root

if __name__ == "__main__":
    ReloadedStoreInstaller().run()
