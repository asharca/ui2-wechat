#!/usr/bin/env python3
"""
微信公众号自动化订阅脚本
"""

import csv
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Set, Optional, Tuple

import uiautomator2 as u2
from uiautomator2 import Device
from uiautomator2.xpath import XMLElement

from logger import setup_logging
from utils import is_url


@dataclass
class PublicAccount:
    """公众号信息数据类"""
    name: str
    unit: str
    desc: str
    article_link: str


class WeChatAutomation:
    """微信公众号自动化类"""

    REGIONS = [
        "内蒙古自治区", "辽宁省", "吉林省", "黑龙江省", "上海市", "江苏省",
        "浙江省", "安徽省", "福建省", "江西省", "山东省", "河南省",
        "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省", "重庆市",
        "四川省", "贵州省", "云南省", "西藏自治区", "陕西省", "甘肃省",
        "青海省", "宁夏回族自治区", "新疆维吾尔自治区"
    ]

    XPATH_SELECTORS = {
        'search_icon': '//*[@content-desc="搜索"]',
        'search_bar': 'android.widget.EditText',
        'account_btn': '//*[@text="账号,按钮,17之2"]',
        'public_account_btn': '//*[@text="公众号"]',
        'court_buttons': '//android.view.View/android.widget.Button[contains(@text, "法院")][1]',
        'subscribe_btn': '@com.tencent.mm:id/amt',
        'subscribed_btn': '@com.tencent.mm:id/anv',
        'message_switch': '//*[@content-desc="切换到发消息"]',
        'more_btn': '@com.tencent.mm:id/coz',
        'first_article_btn': '@com.tencent.mm:id/dyu',
        'alt_article_btn': '@com.tencent.mm:id/cbr',
        'share_btn': '//android.widget.Button[contains(@text, "分享")]',
        'copy_link_btn': '//*[@text="复制链接"]',
        'back_btn': '@com.google.android.apps.nexuslauncher:id/back',
        'search_result': '@search_result',
        'clipboard_toast': '@com.android.systemui:id/clipboard_ui',
        'dismiss_clipboard': '@com.android.systemui:id/dismiss_button',
        'taskbar': '@com.google.android.apps.nexuslauncher:id/taskbar_container'
    }

    def __init__(self, csv_file: str = "public_accounts.csv",
                 operation_delay: Tuple[float, float] = (0.5, 1.0),
                 max_retries: int = 3,
                 max_swipe_retries: int = 3):
        """
        初始化微信自动化实例

        Args:
            csv_file: CSV文件路径
            operation_delay: 操作延迟范围
            max_retries: 最大重试次数
            max_swipe_retries: 最大滑动重试次数
        """
        self.csv_file = Path(csv_file)
        self.max_retries = max_retries
        self.max_swipe_retries = max_swipe_retries

        setup_logging()
        self.logger = logging.getLogger("cwa")

        self.device = self._connect_device(operation_delay)

        self._init_csv()
        self.name_records, self.article_link_records = self._load_existing_records()

    def _connect_device(self, operation_delay: Tuple[float, float]) -> Device:
        """连接设备"""
        try:
            device = u2.connect()
            device.settings["operation_delay"] = operation_delay
            self.logger.info(f"设备连接成功: {device.device_info}")
            return device
        except u2.exceptions.UiAutomationNotConnectedError as e:
            self.logger.error(f"设备连接失败: {e}")
            raise

    def _init_csv(self) -> None:
        """初始化CSV文件"""
        if not self.csv_file.exists():
            with self.csv_file.open('w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['name', 'unit', 'desc', 'article_link'])

    def _load_existing_records(self) -> Tuple[Set[str], Set[str]]:
        """加载现有记录"""
        name_records = set()
        article_link_records = set()

        if self.csv_file.exists():
            try:
                with self.csv_file.open('r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name_records.add(row.get('name', ''))
                        article_link_records.add(row.get('article_link', ''))
            except Exception as e:
                self.logger.error(f"加载现有记录失败: {e}")

        return name_records, article_link_records

    def save_to_csv(self, account: PublicAccount) -> None:
        """保存公众号信息到CSV"""
        try:
            with self.csv_file.open('a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([account.name, account.unit, account.desc, account.article_link])
            self.logger.info(f"保存成功: {account.name}")
        except Exception as e:
            self.logger.error(f"保存失败: {e}")

    @contextmanager
    def _safe_operation(self, operation_name: str):
        """安全操作上下文管理器"""
        try:
            self.logger.debug(f"开始执行: {operation_name}")
            yield
        except Exception as e:
            self.logger.error(f"{operation_name} 执行失败: {e}")
            raise
        finally:
            self.logger.debug(f"完成执行: {operation_name}")

    def _dismiss_clipboard_toast(self) -> None:
        """关闭剪贴板提示"""
        clipboard_toast = self.device.xpath(self.XPATH_SELECTORS['clipboard_toast'])
        if clipboard_toast.exists:
            try:
                self.device.xpath(self.XPATH_SELECTORS['dismiss_clipboard']).click()
                self.device.sleep(0.5)
            except u2.exceptions.XPathElementNotFoundError:
                self.logger.debug("剪贴板提示关闭失败或不存在")

    def _is_element_in_visible_area(self, element: XMLElement) -> bool:
        """检查元素是否在可见区域内"""
        try:
            search_result_view = self.device.xpath(self.XPATH_SELECTORS['search_result']).get()
            taskbar = self.device.xpath(self.XPATH_SELECTORS['taskbar'])

            _, _, _, search_bottom = search_result_view.bounds
            _, taskbar_top, _, _ = taskbar.bounds if taskbar.exists else (0, float('inf'), 0, 0)

            _, element_y = element.center()

            return search_bottom <= element_y <= taskbar_top
        except Exception as e:
            self.logger.warning(f"检查元素可见性失败: {e}")
            return True  # 默认认为可见

    def _click_if_visible(self, element: XMLElement) -> bool:
        """如果元素可见则点击"""
        self._dismiss_clipboard_toast()

        if self._is_element_in_visible_area(element):
            element.click()
            return True
        return False

    def _drag_to_next_page(self) -> None:
        """拖拽到下一页"""
        try:
            search_result_view = self.device.xpath(self.XPATH_SELECTORS['search_result']).get()
            search_result_first = self.device.xpath(
                f"{self.XPATH_SELECTORS['search_result']}/android.view.View"
            ).get()

            _, _, rx, ry = search_result_view.bounds
            lx, ly, _, _ = search_result_first.bounds

            self.logger.debug("执行拖拽操作")
            self.device.drag(rx - 20, ry - 20, lx, ly)
            self.device.sleep(1)  # 等待拖拽完成
        except Exception as e:
            self.logger.error(f"拖拽失败: {e}")

    def _parse_button_text(self, button_text: str) -> Optional[Tuple[str, str, str]]:
        """解析按钮文本，提取名称、单位和描述"""
        try:
            parts = button_text.split()
            if len(parts) < 4:
                return None
            return parts[0], parts[1], parts[3]
        except Exception as e:
            self.logger.error(f"解析按钮文本失败: {button_text}, {e}")
            return None

    def _subscribe_to_account(self, name: str) -> bool:
        """订阅公众号"""
        for attempt in range(1, self.max_retries + 1):
            subscribe_btn = self.device.xpath(self.XPATH_SELECTORS['subscribe_btn'])
            subscribed_btn = self.device.xpath(self.XPATH_SELECTORS['subscribed_btn'])
            message_switch = self.device.xpath(self.XPATH_SELECTORS['message_switch'])

            if subscribe_btn.exists:
                subscribe_btn.click()
                self.device.sleep(1)

                if subscribed_btn.exists:
                    self.logger.info(f"订阅成功: {name} (尝试 {attempt})")
                    return False  # 不是已订阅页面
                else:
                    self.logger.warning(f"订阅失败: {name} (尝试 {attempt})")
                    if attempt < self.max_retries:
                        self.device.sleep(1)

            elif message_switch.exists or subscribed_btn.exists:
                self.logger.info(f"已订阅: {name}")
                return message_switch.exists  # 返回是否是订阅页面
            else:
                self.logger.warning(f"未找到订阅按钮: {name} (尝试 {attempt})")
                if attempt < self.max_retries:
                    self.device.sleep(1)

        return False

    def _get_article_link(self, is_subscribe_page: bool) -> Optional[str]:
        """获取文章链接"""
        try:
            # 如果是订阅页面，需要点击更多按钮
            if is_subscribe_page:
                more_btn = self.device.xpath(self.XPATH_SELECTORS['more_btn'])
                if more_btn.exists:
                    more_btn.click()
                else:
                    self.logger.warning("未找到更多按钮")
                    return None

            # 查找第一篇文章按钮
            first_article_btn = (self.device.xpath(self.XPATH_SELECTORS['first_article_btn']) |
                                 self.device.xpath(self.XPATH_SELECTORS['alt_article_btn']))

            if not first_article_btn.exists:
                self.logger.warning("未找到文章按钮")
                return None

            first_article_btn.click()
            self.device.sleep(0.5)

            if not self.device.xpath(self.XPATH_SELECTORS['share_btn']).click_exists():
                self.logger.warning("未找到分享按钮")
                return None

            self.device.sleep(0.5)

            if not self.device.xpath(self.XPATH_SELECTORS['copy_link_btn']).click_exists():
                self.logger.warning("未找到复制链接按钮")
                return None

            return self.device.clipboard

        except Exception as e:
            self.logger.error(f"获取文章链接失败: {e}")
            return None

    def _navigate_back(self, steps: int = 3) -> None:
        """导航返回指定步数"""
        for i in range(steps):
            try:
                self.device.xpath(self.XPATH_SELECTORS['back_btn']).click()
                self.device.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"返回步骤 {i+1} 失败: {e}")

    def _process_court_account(self, button: XMLElement) -> bool:
        """处理单个法院公众号"""
        button_text = button.info.get("text", "unknown")
        parsed = self._parse_button_text(button_text)

        if not parsed:
            self.logger.error(f"按钮文本格式错误: {button_text}")
            return True

        name, unit, desc = parsed

        if "法院" not in name:
            return True

        if name in self.name_records:
            self.logger.info(f"账号已存在: {name}")
            return True

        self.logger.info(f"发现公众号: {name}")

        if not self._click_if_visible(button):
            self.logger.warning(f"无法点击: {name}")
            return True

        is_subscribe_page = self._subscribe_to_account(name)

        article_link = self._get_article_link(is_subscribe_page)

        if not article_link or not is_url(article_link):
            self.logger.error(f"无效的文章链接: {article_link}")
            self._navigate_back(4 if is_subscribe_page else 3)
            return True

        if article_link in self.article_link_records:
            self.logger.error(f"文章链接重复: {article_link}")
            self._navigate_back(4 if is_subscribe_page else 3)
            return True

        account = PublicAccount(name, unit, desc, article_link)
        self.save_to_csv(account)

        # 更新记录集合
        self.name_records.add(name)
        self.article_link_records.add(article_link)

        # 返回上级页面
        self._navigate_back(4 if is_subscribe_page else 3)

        return True

    def _search_region_courts(self, region: str) -> None:
        """搜索指定地区的法院公众号"""
        search_keyword = f"{region}法院"
        self.logger.info(f"开始搜索: {search_keyword}")

        with self._safe_operation("启动微信"):
            self.device.app_start("com.tencent.mm", stop=True)

        with self._safe_operation("点击搜索图标"):
            if not self.device.xpath(self.XPATH_SELECTORS['search_icon']).click_exists(timeout=10):
                raise RuntimeError("未找到搜索图标")

        with self._safe_operation("输入搜索关键字"):
            search_bar = self.device(className=self.XPATH_SELECTORS['search_bar'])
            if search_bar.wait(timeout=10):
                search_bar.set_text(search_keyword)
                self.logger.info(f"输入搜索关键字: {search_keyword}")
            else:
                raise RuntimeError("未找到搜索栏")

        with self._safe_operation("点击搜索结果"):
            result_xpath = f"(//*[@text='{search_keyword}'])[2]"
            if not self.device.xpath(result_xpath).click_exists(timeout=10):
                raise RuntimeError("未找到搜索结果")

        with self._safe_operation("点击账号按钮"):
            if not self.device.xpath(self.XPATH_SELECTORS['account_btn']).click_exists(timeout=10):
                raise RuntimeError("未找到账号按钮")

        with self._safe_operation("点击公众号按钮"):
            if not self.device.xpath(self.XPATH_SELECTORS['public_account_btn']).click_exists(timeout=10):
                raise RuntimeError("未找到公众号按钮")

        self.device.sleep(5)

        # 处理法院公众号
        self._process_court_accounts()

        self.logger.info(f"{region} 处理完成!")

    def _process_court_accounts(self) -> None:
        """处理所有法院公众号"""
        court_buttons = self.device.xpath(self.XPATH_SELECTORS['court_buttons'])
        swipe_retry_count = 0
        last_button_text = ""

        while court_buttons.exists and swipe_retry_count < self.max_swipe_retries:
            current_button_text = court_buttons.get_text()

            if last_button_text == current_button_text:
                self.logger.warning(f"滑动无效，重试次数: {swipe_retry_count + 1}")
                swipe_retry_count += 1
            else:
                swipe_retry_count = 0

            last_button_text = current_button_text

            # 处理当前页面的所有法院公众号
            for button in court_buttons.all():
                if not self._process_court_account(button):
                    return

            # 拖拽到下一页
            self._drag_to_next_page()

            # 重新查找按钮（页面已更新）
            court_buttons = self.device.xpath(self.XPATH_SELECTORS['court_buttons'])

        if swipe_retry_count >= self.max_swipe_retries:
            self.logger.warning("达到最大滑动重试次数")
        else:
            self.logger.info("当前页面无更多包含'法院'的公众号")

    def run_all_regions(self) -> None:
        """运行所有地区的公众号搜索"""
        self.logger.info("开始批量处理所有地区")

        for i, region in enumerate(self.REGIONS, 1):
            try:
                self.logger.info(f"处理进度: {i}/{len(self.REGIONS)} - {region}")
                self._search_region_courts(region)
            except Exception as e:
                self.logger.error(f"处理 {region} 时发生错误: {e}")
                continue  # 继续处理下一个地区

        self.logger.info("所有地区处理完成!")

    def run_single_region(self, region: str) -> None:
        """运行单个地区的公众号搜索"""
        if region not in self.REGIONS:
            self.logger.error(f"不支持的地区: {region}")
            return

        try:
            self._search_region_courts(region)
        except Exception as e:
            self.logger.error(f"处理 {region} 时发生错误: {e}")


def main():
    """主函数"""
    # 创建自动化实例
    automation = WeChatAutomation(
        csv_file="public_accounts.csv",
        operation_delay=(0.5, 1.0),
        max_retries=3,
        max_swipe_retries=3
    )

    # 运行所有地区
    automation.run_all_regions()

    # 或者运行单个地区
    # automation.run_single_region("广东省")


if __name__ == "__main__":
    main()