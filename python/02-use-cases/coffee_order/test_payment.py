#!/usr/bin/env python3
"""
Test Alipay payment redirection page functionality
"""

import time
import webbrowser

import requests

BASE_URL = "http://localhost:8001"


def test_create_order():
    """Create a new order and return the order details."""
    print("📝 Create Order...")

    order_data = {
        "amount": 99.99,
        "currency": "CNY",
        "description": "Test Order Using Alipay",
    }

    response = requests.post(f"{BASE_URL}/api/orders", json=order_data)

    if response.status_code == 200:
        order_info = response.json()
        print("✅ 订单创建成功！")
        print(f"   订单ID: {order_info['id']}")
        print(f"   金额: ¥{order_info['amount']}")
        print(f"   支付URL: {order_info['paymentUrl']}")
        print(f"   二维码URL: {order_info['qrDataUrl'][:50]}...")
        return order_info
    else:
        print(f"❌ 订单创建失败: {response.status_code}")
        print(response.text)
        return None


def test_get_order(order_id):
    """测试获取订单信息"""
    print(f"\n🔍 获取订单信息: {order_id}")

    response = requests.get(f"{BASE_URL}/api/orders/{order_id}")

    if response.status_code == 200:
        order_info = response.json()
        print("✅ 订单信息获取成功！")
        print(f"   状态: {order_info['status']}")
        print(f"   金额: ¥{order_info['amount']}")
        return order_info
    else:
        print(f"❌ 获取订单信息失败: {response.status_code}")
        return None


def test_payment_page(order_id):
    """测试支付页面"""
    print(f"\n💳 打开支付页面: {order_id}")

    payment_url = f"{BASE_URL}/pay/alipay/{order_id}"
    print(f"   支付页面URL: {payment_url}")

    # 在浏览器中打开支付页面
    webbrowser.open(payment_url)
    print("   🌐 已在浏览器中打开支付页面")

    return payment_url


def test_payment_confirmation(order_id):
    """测试支付确认"""
    print(f"\n✅ 模拟支付确认: {order_id}")

    payment_data = {"status": "completed"}

    response = requests.post(f"{BASE_URL}/api/orders/{order_id}/pay", json=payment_data)

    if response.status_code == 200:
        result = response.json()
        print("✅ 支付确认成功！")
        print(f"   订单状态: {result['status']}")
        return result
    else:
        print(f"❌ 支付确认失败: {response.status_code}")
        print(response.text)
        return None


def test_order_cancellation(order_id):
    """测试订单取消"""
    print(f"\n❌ 测试订单取消: {order_id}")

    response = requests.post(f"{BASE_URL}/api/orders/{order_id}/cancel")

    if response.status_code == 200:
        result = response.json()
        print("✅ 订单取消成功！")
        print(f"   订单状态: {result['status']}")
        return result
    else:
        print(f"❌ 订单取消失败: {response.status_code}")
        print(response.text)
        return None


def main():
    """主测试函数"""
    print("🚀 开始测试支付宝支付功能")
    print("=" * 50)

    try:
        # 1. 创建订单
        order_info = test_create_order()
        if not order_info:
            return

        order_id = order_info["id"]

        # 2. 获取订单信息
        test_get_order(order_id)

        # 3. 打开支付页面
        test_payment_page(order_id)

        print("\n⏳ 等待用户操作...")
        print("   您可以：")
        print("   - 点击'模拟支付成功'按钮")
        print("   - 点击'取消支付'按钮")
        print("   - 等待15分钟超时")

        # 4. 等待一段时间后检查订单状态
        print("\n⏰ 10秒后将自动检查订单状态...")
        time.sleep(10)

        # 5. 再次获取订单信息
        final_order = test_get_order(order_id)
        if final_order:
            print(f"\n📊 最终订单状态: {final_order['status']}")

        print("\n✅ 测试完成！")

    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")


if __name__ == "__main__":
    main()
