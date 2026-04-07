#!/usr/bin/env python3
"""
WireGuard Manager - GUI приложение для управления WireGuard
Автор: для Нурали брата (Адаптировано для OCR Service)
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import os
import json
import stat
import getpass
import time
import re

CREDENTIALS_FILE = os.path.expanduser("~/.wg_credentials_ocr")
WG_CONFIG_FILE = "/etc/wireguard/wg0.conf"

# Данные сервера по умолчанию
DEFAULT_SERVER = "172.16.252.32"
DEFAULT_USERNAME = "yoyo"
DEFAULT_PASSWORD = ""  # Пароль не хранится - вводите вручную


class WireGuardManager:
    def __init__(self, root):
        self.root = root
        self.root.title("WireGuard Manager (OCR Service)")
        self.root.geometry("500x400")
        self.root.resizable(True, True)
        
        # Переменные
        self.username_var = tk.StringVar(value=DEFAULT_USERNAME)
        self.password_var = tk.StringVar(value=DEFAULT_PASSWORD)
        self.save_credentials_var = tk.BooleanVar(value=True)
        self.current_user = getpass.getuser()
        self.server_var = tk.StringVar(value=DEFAULT_SERVER)
        
        # Загрузка сохранённых учётных данных
        self.load_credentials()
        
        # Создание интерфейса
        self.create_login_frame()
        self.create_control_frame()
        self.create_status_frame()
        
        # Обновление статуса при запуске
        self.update_status()
        
    def create_login_frame(self):
        """Создание рамки входа"""
        login_frame = ttk.LabelFrame(self.root, text="Учётные данные", padding=10)
        login_frame.pack(fill="x", padx=10, pady=5)
        
        # Сервер
        ttk.Label(login_frame, text="Сервер:").grid(row=0, column=0, sticky="w", pady=5)
        self.server_entry = ttk.Entry(login_frame, textvariable=self.server_var, width=30)
        self.server_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # Логин
        ttk.Label(login_frame, text="Логин:").grid(row=1, column=0, sticky="w", pady=5)
        self.username_entry = ttk.Entry(login_frame, textvariable=self.username_var, width=30)
        self.username_entry.grid(row=1, column=1, padx=5, pady=5)
        
        # Пароль
        ttk.Label(login_frame, text="Пароль:").grid(row=2, column=0, sticky="w", pady=5)
        self.password_entry = ttk.Entry(login_frame, textvariable=self.password_var, show="*", width=30)
        self.password_entry.grid(row=2, column=1, padx=5, pady=5)
        
        # Чекбокс сохранения
        ttk.Checkbutton(
            login_frame, 
            text="Сохранить для быстрого входа",
            variable=self.save_credentials_var
        ).grid(row=3, column=1, sticky="w", pady=5)
        
        # Кнопка сохранения
        ttk.Button(
            login_frame, 
            text="Сохранить",
            command=self.save_credentials
        ).grid(row=4, column=1, sticky="e", pady=5)
        
    def create_control_frame(self):
        """Создание рамки управления"""
        control_frame = ttk.LabelFrame(self.root, text="Управление WireGuard", padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)

        # Кнопки управления
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack()

        self.connect_btn = ttk.Button(
            btn_frame,
            text="🔌 Подключить",
            command=self.connect_wg,
            style="Accent.TButton"
        )
        self.connect_btn.pack(side="left", padx=5, pady=5)

        self.disconnect_btn = ttk.Button(
            btn_frame,
            text="❌ Отключить",
            command=self.disconnect_wg
        )
        self.disconnect_btn.pack(side="left", padx=5, pady=5)

        self.refresh_btn = ttk.Button(
            btn_frame,
            text="🔄 Обновить статус",
            command=self.update_status
        )
        self.refresh_btn.pack(side="left", padx=5, pady=5)

        # Кнопка терминала - отдельная строка
        term_frame = ttk.Frame(control_frame)
        term_frame.pack(pady=5)

        self.terminal_btn = ttk.Button(
            term_frame,
            text="💻 Терминал на сервере",
            command=self.open_server_terminal
        )
        self.terminal_btn.pack(side="left", padx=5, pady=5)
        
    def create_status_frame(self):
        """Создание рамки статуса"""
        status_frame = ttk.LabelFrame(self.root, text="Статус WireGuard", padding=10)
        status_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Индикатор статуса
        self.status_label = ttk.Label(status_frame, text="●", font=("Arial", 24))
        self.status_label.pack()
        
        # Текстовое описание статуса
        self.status_text = ttk.Label(status_frame, text="Неизвестно", font=("Arial", 12, "bold"))
        self.status_text.pack()
        
        # Детальная информация
        self.info_text = scrolledtext.ScrolledText(status_frame, height=8, width=60, font=("Courier", 9))
        self.info_text.pack(fill="both", expand=True, pady=5)
        
    def load_credentials(self):
        """Загрузка сохранённых учётных данных"""
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, 'r') as f:
                    creds = json.load(f)
                    if creds.get('username'):
                        self.username_var.set(creds['username'])
                    if creds.get('password'):
                        self.password_var.set(creds['password'])
                    if creds.get('server'):
                        self.server_var.set(creds['server'])
            except (json.JSONDecodeError, IOError):
                pass
                
    def save_credentials(self):
        """Сохранение учётных данных"""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        server = self.server_var.get().strip()

        if not username:
            messagebox.showwarning("Предупреждение", "Введите логин!")
            return
            
        try:
            creds = {
                'username': username,
                'password': password if self.save_credentials_var.get() else '',
                'server': server if self.save_credentials_var.get() else DEFAULT_SERVER
            }
            
            # Сохранение с безопасными правами (только владелец)
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump(creds, f, indent=2)
            os.chmod(CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 600
            
            messagebox.showinfo("Успех", "Учётные данные сохранены!")
        except IOError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")
            
    def connect_wg(self):
        """Подключение WireGuard"""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            messagebox.showwarning("Предупреждение", "Введите логин и пароль!")
            return

        # Сохранение при подключении если выбрано
        if self.save_credentials_var.get():
            self.save_credentials()

        self.info_text.delete(1.0, "end")
        self.info_text.insert("end", f"[{self.get_timestamp}] Попытка подключения...\n")
        self.info_text.see("end")

        try:
            # Проверка статуса WireGuard (требуется sudo)
            result = subprocess.run(
                ["sudo", "wg", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0 or not result.stdout.strip():
                # Интерфейс не активен - поднимаем
                up_result = subprocess.run(
                    ["sudo", "wg-quick", "up", "wg0"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if up_result.returncode != 0:
                    raise Exception(f"wg-quick up failed: {up_result.stderr}")
                self.info_text.insert("end", f"[{self.get_timestamp}] Интерфейс wg0 поднят\n")
            else:
                self.info_text.insert("end", f"[{self.get_timestamp}] WireGuard уже активен\n")

            # Небольшая задержка для обновления статуса
            time.sleep(1)
            self.update_status()
            messagebox.showinfo("Успех", "WireGuard подключён!")

        except subprocess.TimeoutExpired:
            self.info_text.insert("end", f"[{self.get_timestamp}] Таймаут операции\n")
            messagebox.showerror("Ошибка", "Таймаут при подключении!")
        except Exception as e:
            self.info_text.insert("end", f"[{self.get_timestamp}] Ошибка: {e}\n")
            messagebox.showerror("Ошибка", f"Не удалось подключиться: {e}")

        self.info_text.see("end")
        
    def disconnect_wg(self):
        """Отключение WireGuard"""
        self.info_text.delete(1.0, "end")
        self.info_text.insert("end", f"[{self.get_timestamp}] Отключение...\n")

        try:
            subprocess.run(
                ["sudo", "wg-quick", "down", "wg0"],
                capture_output=True,
                text=True,
                timeout=30
            )
            time.sleep(1)
            self.update_status()
            messagebox.showinfo("Успех", "WireGuard отключён!")
        except subprocess.TimeoutExpired:
            self.info_text.insert("end", f"[{self.get_timestamp}] Таймаут операции\n")
            messagebox.showerror("Ошибка", "Таймаут при отключении!")
        except Exception as e:
            self.info_text.insert("end", f"[{self.get_timestamp}] Ошибка: {e}\n")
            messagebox.showerror("Ошибка", f"Не удалось отключиться: {e}")

        self.info_text.see("end")

    def open_server_terminal(self):
        """Открытие терминала с подключением к серверу"""
        # Проверяем статус WireGuard (требуется sudo)
        try:
            result = subprocess.run(
                ["sudo", "wg", "show"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0 or not result.stdout.strip():
                messagebox.showwarning("Предупреждение", "Сначала подключите WireGuard!")
                return
        except Exception:
            messagebox.showwarning("Предупреждение", "Сначала подключите WireGuard!")
            return

        # Получаем адрес сервера из поля ввода
        server = self.server_var.get().strip() or DEFAULT_SERVER

        self.info_text.insert("end", f"[{self.get_timestamp}] Открытие терминала на {server}...\n")
        self.info_text.see("end")

        # Получаем логин из учётных данных
        username = self.username_var.get().strip() or DEFAULT_USERNAME

        # Запуск терминала через скрипт (пароль вводится вручную)
        try:
            ssh_script = os.path.expanduser(f"~/ssh_to_server_ocr.sh")
            with open(ssh_script, "w") as f:
                f.write(f"#!/bin/bash\nssh {username}@{server}\n")
            os.chmod(ssh_script, 0o755)

            # Запуск через gnome-terminal с bash
            subprocess.Popen([
                'gnome-terminal',
                '--title', f'SSH - {server}',
                '--', 'bash', ssh_script
            ], start_new_session=True)

            self.info_text.insert("end", f"[{self.get_timestamp}] Терминал запущен\n")
            self.info_text.insert("end", f"[{self.get_timestamp}] Введите пароль для SSH, затем: sudo su\n")
        except Exception as e:
            self.info_text.insert("end", f"[{self.get_timestamp}] Ошибка запуска терминала: {e}\n")
            messagebox.showerror("Ошибка", f"Не удалось открыть терминал: {e}")
        
    def update_status(self):
        """Обновление статуса WireGuard"""
        try:
            result = subprocess.run(
                ["sudo", "wg", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                # WireGuard активен
                self.status_label.config(text="●", foreground="green")
                self.status_text.config(text="ПОДКЛЮЧЕНО", foreground="green")
                
                # Очищаем и показываем информацию
                self.info_text.delete(1.0, "end")
                self.info_text.insert("end", f"[{self.get_timestamp}] Статус: АКТИВЕН\n\n")
                self.info_text.insert("end", result.stdout + "\n")
            else:
                # WireGuard не активен
                self.status_label.config(text="●", foreground="red")
                self.status_text.config(text="ОТКЛЮЧЕНО", foreground="red")
                self.info_text.delete(1.0, "end")
                self.info_text.insert("end", f"[{self.get_timestamp}] Статус: НЕ АКТИВЕН\n")

        except Exception as e:
            self.status_label.config(text="●", foreground="gray")
            self.status_text.config(text="НЕИЗВЕСТНО", foreground="gray")
            self.info_text.delete(1.0, "end")
            self.info_text.insert("end", f"[{self.get_timestamp}] Ошибка получения статуса: {e}\n")

        self.info_text.see("end")
        
    @property
    def get_timestamp(self):
        """Получение временной метки"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")


def main():
    root = tk.Tk()
    
    # Настройка стиля
    style = ttk.Style()
    style.theme_use('clam')
    
    # Настройка цветов
    style.configure("Accent.TButton", foreground="white", background="green")
    
    app = WireGuardManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()
