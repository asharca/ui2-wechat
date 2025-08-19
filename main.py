import copy

import uiautomator2 as u2
import logging
import csv
import os
from uiautomator2 import Device
from uiautomator2.xpath import XMLElement
from utils import is_url
from logger import setup_logging

setup_logging()
logger = logging.getLogger("cwa")

regions = [
    "内蒙古自治区",
    "辽宁省",
    "吉林省",
    "黑龙江省",
    "上海市",
    "江苏省",
    "浙江省",
    "安徽省",
    "福建省",
    "江西省",
    "山东省",
    "河南省",
    "湖北省",
    "湖南省",
    "广东省",
    "广西壮族自治区",
    "海南省",
    "重庆市",
    "四川省",
    "贵州省",
    "云南省",
    "西藏自治区",
    "陕西省",
    "甘肃省",
    "青海省",
    "宁夏回族自治区",
    "新疆维吾尔自治区",
]

csv_file = "public_accounts.csv"
csv_header = ["name", "unit", "desc", "article_link"]
if not os.path.exists(csv_file):
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)

name_records = set()
article_link_records = set()
if os.path.exists(csv_file):
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name_records.add(row["name"])
            article_link_records.add(row["article_link"])


def save_to_csv(public_name: str, u: str, desc: str, link: str):
    """Save public account info to CSV."""
    with open(csv_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([public_name, u, desc, link])


def drap_to_next_page(device: Device):
    search_result_view = device.xpath('//*[@resource-id="search_result"]').get()
    search_result_first_view = (
        device.xpath('//*[@resource-id="search_result"]')
        .child("/android.view.View")
        .get()
    )
    _, _, rx, ry = search_result_view.bounds
    lx, ly, _, _ = search_result_first_view.bounds
    logger.info("Drag to the next page")
    device.drag(rx - 20, ry - 20, lx, ly)


def click_public_account_if_cover(device: Device, btn: XMLElement):
    clipboard_toast = device.xpath(
        '//*[@resource-id="com.android.systemui:id/clipboard_ui"]'
    )
    if clipboard_toast.exists:
        try:
            device.xpath(
                '//*[@resource-id="com.android.systemui:id/dismiss_button"]'
            ).click()
        except u2.exceptions.XPathElementNotFoundError:
            logger.warning("Cancel clipboard failed, maybe not exist")
    device.sleep(0.5)
    search_result_first_view = (
        device.xpath('//*[@resource-id="search_result"]')
        .child("/android.view.View")
        .get()
    )
    navigation_box = device.xpath(
        "@com.google.android.apps.nexuslauncher:id/taskbar_container"
    )
    _, _, _, rry = search_result_first_view.bounds
    _, nly, _, _ = navigation_box.bounds
    _, y = btn.center()
    if y < rry:
        return False
    elif y > nly:
        return False
    else:
        btn.click()
        return True


try:
    d = u2.connect()
    logger.info("Connected successful: %s", d.device_info)
    d.settings["operation_delay"] = (0.5, 1)
except u2.exceptions.UiAutomationNotConnectedError as e:
    logger.error("Connected failed: %s", e)
    exit(1)


def main(region: str):
    region = region + "法院"
    logger.info("Start Wechat...")
    d.app_start("com.tencent.mm", stop=True)

    logger.info("Wait search icon")
    search_icon = d.xpath('//*[@content-desc="搜索"]')
    if not search_icon.click_exists():
        logger.error("未找到搜索图标")
        exit(1)

    logger.info("Wait search menu")
    search_bar = d(className="android.widget.EditText")
    if search_bar.wait():
        logger.info(f"输入搜索关键字: {region}")
        search_bar.set_text(f"{region}")
    else:
        logger.error("未找到搜索栏")
        exit(1)

    logger.info("Wait search result")
    result = d.xpath(f"(//*[@text='{region}'])[2]")
    if not result.click_exists():
        logger.error("未找到搜索结果")
        exit(1)

    logger.info("wait account button")
    account_btn = d.xpath('//*[@text="账号,按钮,17之2"]')
    if not account_btn.click_exists():
        logger.error("未找到账号button")
        exit(1)

    logger.info("wait public account button")
    office_btn = d.xpath('//*[@text="公众号"]')
    if not office_btn.click_exists():
        logger.error("未找到公众号button")
        exit(1)

    d.sleep(5)
    court_buttons = d.xpath(
        '//android.view.View/android.widget.Button[contains(@text, "法院")][1]'
    )

    err_tol = 0
    max_court_retires = 0
    cache_court_text = ""

    while court_buttons.exists:
        if max_court_retires == 3:
            logger.warning("Reached the max retires")
            max_court_retires = 0
            break

        if cache_court_text == court_buttons.get_text():
            logger.error("Swipe error: %s", cache_court_text)
            max_court_retires += 1
        cache_court_text = court_buttons.get_text()

        for button in court_buttons.all():
            if err_tol != 0:
                err_tol -= 1
                continue
            button_text = button.info.get("text", "unknown")
            text = button_text.split()
            try:
                name = text[0]
                unit = text[1]
                desc = text[3]
            except IndexError as e:
                logger.error("Button text is wrong: %s", e)
                continue
            if "法院" in name:
                logger.info("Founded: %s", name)
            else:
                continue
            if name in name_records:
                logger.info("The name is existed: %s", name)
                continue

            if not click_public_account_if_cover(d, button):
                logger.warning("Can't click: %s", name)
                continue

            max_retries = 3
            is_subscribe_page = False

            for attempt in range(1, max_retries + 1):
                subscribe_button = d.xpath('//*[@resource-id="com.tencent.mm:id/amt"]')
                subscribed_button = d.xpath('//*[@resource-id="com.tencent.mm:id/anv"]')

                if subscribe_button.exists:
                    subscribe_button.click()
                    d.sleep(1)

                    if subscribed_button.exists:
                        logger.info(
                            "Subscribe successful: %s (attempt %d)", name, attempt
                        )
                        break
                    else:
                        logger.warning(
                            "Subscribe failed: %s (attempt %d)", name, attempt
                        )
                        d.sleep(1)
                elif d.xpath("//*[@content-desc='切换到发消息']").exists:
                    logger.info("Already subscribed: %s", name)
                    is_subscribe_page = True
                    break
                elif subscribed_button.exists:
                    logger.info("Already subscribed: %s", name)
                    break
                else:
                    logger.warning(
                        "Subscribe button not found: %s (attempt %d)", name, attempt
                    )
                    d.sleep(1)

            if is_subscribe_page:
                more_btn = d.xpath('//*[@resource-id="com.tencent.mm:id/coz"]')
                if not more_btn.exists:
                    logger.warning("Avatar button not found")
                more_btn.click()
            first_article_btn = d.xpath("@com.tencent.mm:id/dyu") | d.xpath(
                "@com.tencent.mm:id/cbr"
            )
            d.sleep(0.5)
            if not first_article_btn.exists:
                logger.warning("Article link button not found")
            first_article_btn.click()
            d.xpath('//android.widget.Button[contains(@text, "分享")]').click_exists()
            d.sleep(0.5)
            d.xpath('//*[@text="复制链接"]').click_exists()
            article_link = d.clipboard
            if is_url(article_link):
                if article_link not in article_link_records:
                    save_to_csv(name, unit, desc, article_link)
                    name_records.add(name)
                    article_link_records.add(article_link)
                    logger.info(
                        "Save to csv file: %s, article_link: %s", name, article_link
                    )
                else:
                    logger.error("Article url is duplicated: %s", article_link)
                    continue
            else:
                logger.error("Article url is not allowed: %s", article_link)
                continue
            # d.press('back')
            if is_subscribe_page:
                d.xpath(
                    '//*[@resource-id="com.google.android.apps.nexuslauncher:id/back"]'
                ).click()
                d.sleep(0.5)
            # d.press('back')
            d.xpath(
                '//*[@resource-id="com.google.android.apps.nexuslauncher:id/back"]'
            ).click()
            d.sleep(0.5)
            # d.press("back")
            d.xpath(
                '//*[@resource-id="com.google.android.apps.nexuslauncher:id/back"]'
            ).click()
            d.sleep(0.5)
        drap_to_next_page(d)
        err_tol += 1
    else:
        logger.info("当前页面无更多包含‘法院’的公众号")

    logger.info(f"{region} done!")


if __name__ == "__main__":
    for region in regions:
        main(region)
