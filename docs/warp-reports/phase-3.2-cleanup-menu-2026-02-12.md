# Phase 3.2: پاکسازی منوی Sidebar

## تاریخ و زمان
2026-02-12 06:50:00

## خلاصه تغییرات
ماژول‌های خالی و تکراری از سیستم حذف شدند. فایل‌های مربوطه از دیسک پاک شدند و رکوردهای نامعتبر از دیتابیس حذف گردیدند. همچنین منطق ساخت منوی Sidebar بهبود یافت تا از نمایش آیتم‌های تکراری جلوگیری شود و فقط ماژول‌های دارای کانفیگ معتبر نمایش داده شوند.

## فایل‌ها و فولدرهای حذف شده
- /opt/admin-panel/core-app/modules/backup/
- /opt/admin-panel/core-app/modules/fileserver/
- /opt/admin-panel/core-app/modules/fog/
- /opt/admin-panel/core-app/modules/pfsense/
- /opt/admin-panel/core-app/modules/users/
- (رکورد دیتابیس) ماژول dashboard (به دلیل نداشتن فایل کانفیگ)

## فایل‌های تغییر یافته
- **utils/module_registry.py**: اضافه شدن چک `config.json` قبل از ثبت ماژول در دیتابیس.
- **utils/context_processors.py**: 
  - حذف آیتم دستی "Administration" برای جلوگیری از تکرار.
  - اضافه شدن تابع `module_exists` برای بررسی وجود فیزیکی ماژول قبل از نمایش در منو.
  - فیلتر کردن لیست ماژول‌های دریافتی از دیتابیس با تابع `module_exists`.

## تغییرات Database
```sql
DELETE FROM permissions WHERE module_id IN (2, 3, 4, 5, 6, 7);
DELETE FROM modules WHERE id IN (2, 3, 4, 5, 6, 7);
-- (IDs removed: backup, fileserver, fog, pfsense, users, dashboard)
```
