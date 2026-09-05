from typing import List, Dict, Optional, Any
from app.schemas.merchant import MerchantProduct, ProductFeatureMap

MERCHANT_CATALOGS: Dict[str, Dict[str, Any]] = {
    "merchant_electromax": {
        "merchant_id": "merchant_electromax",
        "merchant_name": "ElectroMax Audio",
        "agent_name": "ElectroMax Commercial Agent",
        "seller_rating": 4.8,
        "endpoint": "https://api.electromax.example/a2a/v1",
        "products": [
            MerchantProduct(
                product_id="prod_em_001",
                merchant_id="merchant_electromax",
                merchant_name="ElectroMax Audio",
                title="SoundPro X2 ANC Wireless Headphones",
                category="wireless headphones",
                base_price=4299.0,
                currency="INR",
                in_stock=True,
                stock_count=18,
                delivery_days=2,
                seller_rating=4.8,
                image_url="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=80",
                description="Engineered for daily commute. Hybrid Active Noise Cancellation, 32-hour extended battery.",
                features=ProductFeatureMap(
                    noise_cancellation=True,
                    anc_type="Hybrid Active ANC (35dB)",
                    battery_hours=32,
                    fast_charging=True,
                    water_resistance="IPX4",
                    bluetooth_version="5.3",
                    microphone=True,
                    warranty_months=12
                )
            ),
            MerchantProduct(
                product_id="prod_em_002",
                merchant_id="merchant_electromax",
                merchant_name="ElectroMax Audio",
                title="SoundPro Lite Wireless",
                category="wireless headphones",
                base_price=2499.0,
                currency="INR",
                in_stock=True,
                stock_count=45,
                delivery_days=2,
                seller_rating=4.5,
                image_url="https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500&q=80",
                description="Lightweight everyday wireless headphones with punchy bass and passive isolation.",
                features=ProductFeatureMap(
                    noise_cancellation=False,
                    anc_type="Passive Isolation",
                    battery_hours=20,
                    fast_charging=False,
                    water_resistance="IPX2",
                    bluetooth_version="5.1",
                    microphone=True,
                    warranty_months=12
                )
            )
        ]
    },
    "merchant_soundvault": {
        "merchant_id": "merchant_soundvault",
        "merchant_name": "SoundVault Premium Store",
        "agent_name": "SoundVault Smart Commerce Agent",
        "seller_rating": 4.9,
        "endpoint": "https://api.soundvault.example/a2a/v1",
        "products": [
            MerchantProduct(
                product_id="prod_sv_101",
                merchant_id="merchant_soundvault",
                merchant_name="SoundVault Premium Store",
                title="AcoustiQ OverEar Pro Wireless ANC",
                category="wireless headphones",
                base_price=5100.0, # Will dynamically offer discount to ₹4,800 within user ₹5,000 budget
                currency="INR",
                in_stock=True,
                stock_count=12,
                delivery_days=1,
                seller_rating=4.9,
                image_url="https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=500&q=80",
                description="Audiophile-grade 40h battery, Dual Feed-forward ANC, ultra-plush memory foam for long commutes.",
                features=ProductFeatureMap(
                    noise_cancellation=True,
                    anc_type="Dual Feed-Forward Active ANC (40dB)",
                    battery_hours=40,
                    fast_charging=True,
                    water_resistance="IPX5",
                    bluetooth_version="5.3",
                    microphone=True,
                    warranty_months=24
                )
            )
        ]
    },
    "merchant_budgetgizmos": {
        "merchant_id": "merchant_budgetgizmos",
        "merchant_name": "BudgetGizmos Direct",
        "agent_name": "BudgetGizmos Direct Agent",
        "seller_rating": 4.2,
        "endpoint": "https://api.budgetgizmos.example/a2a/v1",
        "products": [
            MerchantProduct(
                product_id="prod_bg_201",
                merchant_id="merchant_budgetgizmos",
                merchant_name="BudgetGizmos Direct",
                title="BassBoom 500 Wireless Over-Ear",
                category="wireless headphones",
                base_price=3900.0,
                currency="INR",
                in_stock=True,
                stock_count=60,
                delivery_days=3,
                seller_rating=4.2,
                image_url="https://images.unsplash.com/photo-1484704849700-f032a568e944?w=500&q=80",
                description="Ultra long 35h battery life and heavy bass tuning. Passive noise isolation only.",
                features=ProductFeatureMap(
                    noise_cancellation=False,
                    anc_type="None (Passive Only)",
                    battery_hours=35,
                    fast_charging=True,
                    water_resistance="None",
                    bluetooth_version="5.0",
                    microphone=True,
                    warranty_months=6
                )
            )
        ]
    },
    "merchant_sonicwave": {
        "merchant_id": "merchant_sonicwave",
        "merchant_name": "SonicWave Tech",
        "agent_name": "SonicWave Autonomous Agent",
        "seller_rating": 4.6,
        "endpoint": "https://api.sonicwave.example/a2a/v1",
        "products": [
            MerchantProduct(
                product_id="prod_sw_301",
                merchant_id="merchant_sonicwave",
                merchant_name="SonicWave Tech",
                title="SonicWave Commute ANC Pro",
                category="wireless headphones",
                base_price=4450.0,
                currency="INR",
                in_stock=True,
                stock_count=8,
                delivery_days=2,
                seller_rating=4.6,
                image_url="https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80",
                description="Dedicated commute profile with ambient pass-through mode and 30h battery.",
                features=ProductFeatureMap(
                    noise_cancellation=True,
                    anc_type="Adaptive ANC (32dB)",
                    battery_hours=30,
                    fast_charging=True,
                    water_resistance="IPX5",
                    bluetooth_version="5.2",
                    microphone=True,
                    warranty_months=12
                )
            )
        ]
    }
}
