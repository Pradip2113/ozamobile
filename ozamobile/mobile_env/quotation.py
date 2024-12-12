import json
import frappe
from frappe import _
from erpnext.utilities.product import get_price
from frappe.utils import cstr, fmt_money
from erpnext.accounts.utils import getdate
from ozamobapp.mobile_env.app_utils import (
    gen_response,
    prepare_json_data,
    get_global_defaults,
    exception_handel,
    get_ess_settings
)
from bs4 import BeautifulSoup
from frappe.utils import (
    cstr,
    get_date_str,
    today,
    nowdate,
    getdate,
    now_datetime,
    get_first_day,
    get_last_day,
    date_diff,
    flt,
    pretty_date,
    fmt_money,
)
from erpnext.accounts.party import get_dashboard_info
from ozamobapp.mobile_env.app import download_pdf

@frappe.whitelist()
def get_quotation_list(start=0, page_length=10, filters=None):
    try:
        global_defaults = get_global_defaults()
        quotation_list = frappe.get_list(
            "Quotation",
            fields=[
                "name",
                "customer_name",
                "DATE_FORMAT(transaction_date, '%d-%m-%Y') as transaction_date",
                "grand_total",
                "status",
                "total_qty",
            ],
            start=start,
            page_length=page_length,
            order_by="modified desc",
            filters=filters,
        )
        for quotation in quotation_list:
            quotation["grand_total"] = fmt_money(
                quotation["grand_total"],
                currency=global_defaults.get("default_currency"),
            )
        gen_response(200, "Quotation list get successfully", quotation_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for Quotation")
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_quotation(name):
    try:
        quotation_doc = json.loads(
            frappe.get_doc("Quotation", name).as_json()
        )
        global_defaults = get_global_defaults()
        transaction_date = getdate(quotation_doc["transaction_date"])
        valid_till = getdate(quotation_doc["valid_till"])
        quotation_doc["transaction_date"] = transaction_date.strftime("%d-%m-%Y")
        quotation_doc["valid_till"] = valid_till.strftime("%d-%m-%Y")
        quotation_data = get_order_details_with_currency(
            quotation_doc, global_defaults.get("default_currency")
        )
        
        # Initialize the data dictionary
        data = {}
        
        for response_field in [
            "name",
            "quotation_to",
            "party_name",
            "transaction_date",
            "valid_till",
            "total_qty",
            "customer_name",
            "shipping_address",
            "contact_email",
            "contact_mobile",
            "company",
            "terms",
        ]:
            quotation_data[response_field] = quotation_doc.get(response_field)
        
        soup = BeautifulSoup(quotation_data['shipping_address'], 'html.parser')
        text = soup.get_text(separator="\n")
        
        # Set the cleaned shipping address in data
        data['shipping_address'] = text 
        
        item_list = []
        for item in quotation_doc.get("items"):
            item["amount"] = fmt_money(
                item.get("amount"), currency=global_defaults.get("default_currency")
            )
            item["rate_currency"] = fmt_money(
                item.get("rate"), currency=global_defaults.get("default_currency")
            )
            item_list.append(
                prepare_json_data(
                    [
                        "item_name",
                        "item_code",
                        "qty",
                        "amount",
                        "rate",
                        "image",
                        "rate_currency",
                    ],
                    item,
                )
            )
        
        quotation_data["items"] = item_list
        quotation_data["allow_edit"] = (
            True if quotation_doc.get("docstatus") == 0 else False
        )
        
        quotation_data["created_by"] = frappe.get_cached_value(
            "User", quotation_doc.get("owner"), "full_name"
        )
        
        dashboard_info = get_dashboard_info("Customer", quotation_doc.get("customer"))
        
        quotation_data["annual_billing"] = fmt_money(
            dashboard_info[0].get("billing_this_year") if dashboard_info else 0.0,
            currency=global_defaults.get("default_currency"),
        )
        
        quotation_data["total_unpaid"] = fmt_money(
            dashboard_info[0].get("total_unpaid") if dashboard_info else 0.0,
            currency=global_defaults.get("default_currency"),
        )
        
        # Return the final response
        return gen_response(200, "Quotation detail retrieved successfully.", quotation_data)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for sales order")
    except Exception as e:
        return exception_handel(e)

def get_attachments(id):
    return frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Quotation", "attached_to_name": id},
        fields=["file_url", "file_name"],
    )

@frappe.whitelist(allow_guest=True)
def get_customer_list():
    try:
        customer_list = frappe.get_list(
            "Mobile App Notification",
            fields=["name", "subject", "description",'creation'],
           
            order_by="creation desc",
        )
        gen_response(200, "Notification list get successfully", customer_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for customer")
    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def get_app_main_group_list():
    try:
        app_main_group_list = frappe.get_list(
            "App Main Group",
            fields=["name", "main_group", "image","description"],  # Enclosed `group` in backticks
            order_by="modified desc",
        )
        gen_response(200, "App Main Group list fetched successfully", app_main_group_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for App Main Group")
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist(allow_guest=True)
def get_app_item_group_list(mainGroup):
    try:
        app_main_group_list = frappe.get_list(
            "App Item Group",
            fields=["name", "item_group", "image","description"],
           filters={'main_group':mainGroup},
            order_by="modified desc",
        )
        gen_response(200, "App Item Group list get successfully", app_main_group_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for App Item Group")
    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def get_app_item_subgroup_list(group):
    try:
        item_group=frappe.db.get_value("App Item Group",{"item_group":group},"name")
        app_main_group_list = frappe.get_list(
            "App Item Subgroup",
            fields=["name", "sub_group", "image","description"],
           filters={'item_group':item_group},
            order_by="modified desc",
        )
        gen_response(200, "App Item Subgroup list get successfully", app_main_group_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for App Item Subgroup")
    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def get_app_item_list(subGroup):
    try:
        sub_group=frappe.db.get_value("App Item Subgroup",{"sub_group":subGroup},"name")
        app_main_group_list = frappe.get_list(
            "Mobile  App Item",
            fields=["name", "main_group", "image","item_code","item_name","length","size","size_inch","sdr","sub_group","item_group"],  # Enclosed `group` in backticks
            filters={'sub_group':sub_group},
            order_by="modified desc",
        )
        gen_response(200, "Mobile App Item list fetched successfully", app_main_group_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for Mobile App Item")
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist(allow_guest=True)
def get_new_arrival_item_list():
    try:
        app_main_group_list = frappe.get_list(
            "Mobile  App Item",
            fields=["name", "main_group", "image","item_code","item_name","length","size","size_inch","sdr","sub_group","item_group"],  # Enclosed `group` in backticks
            filters={'new_arrival':1},
            order_by="modified desc",
        )
        gen_response(200, "Mobile App Item list fetched successfully", app_main_group_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for Mobile App Item")
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist(allow_guest=True)
def get_app_size_item_list(subGroup):
    try:
        app_main_group_list = frappe.get_list(
            "Mobile  App Item",
            fields=["size"],  # Enclosed `group` in backticks
            filters={'sub_group':subGroup},
            order_by="modified desc",
        )
        gen_response(200, "Mobile App Item list fetched successfully", app_main_group_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for Mobile App Item")
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def company():
    try:
        global_defaults = get_global_defaults()

        data = json.loads(
                frappe.get_doc("Company", global_defaults.get("default_company")).as_json()
            )
            
        company_info = {
            "name": data.get("name"),
            "owner": data.get("owner"),
            "creation_date": data.get("creation"),
            "modified_date": data.get("modified"),
            "modified_by": data.get("modified_by"),
            "company_name": data.get("company_name"),
            "abbreviation": data.get("abbr"),
            "default_currency": data.get("default_currency"),
            "country": data.get("country"),
            "gstin": data.get("gstin"),
            "pan": data.get("pan"),
            "phone_no": data.get("phone_no"),
            "email": data.get("email"),
            "website": data.get("website"),
            "total_monthly_sales": data.get("total_monthly_sales"),
            "credit_limit": data.get("credit_limit")
        }

        gen_response(200, "Company get successfully", company_info)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for item")
    except Exception as e:
        exception_handel(e)

@frappe.whitelist()
def get_item_list(item_group=None):
    try:
        filters = []
        filters.append(["Item", "disabled", "=", 0])
        filters.append(["Item", "is_sales_item", "=", 1])
        filters.append(["Item", "has_variants", "=", 0])
        filters.append(["Item", "item_group", "=", item_group])
        item_list = frappe.get_list(
            "Item", fields=["name", "item_name", "item_code", "image","sales_uom",
                "stock_uom","description"], filters=filters
        )
        items = get_items_rate(item_list)
        gen_response(200, "Item list get successfully", items)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for item")
    except Exception as e:
        exception_handel(e)


def get_items_rate(items):
    global_defaults = get_global_defaults()
    ess_settings = get_ess_settings()
    price_list = ess_settings.get("default_price_list")
    if not price_list:
        frappe.throw(_("Please set price list in ess settings."))
    for item in items:
        item["uom"]=item.sales_uom if item.sales_uom else item.stock_uom
        item_price = frappe.get_all(
            "Item Price",
            filters={"item_code": item.name, "price_list": price_list},
            fields=["price_list_rate"],
        )
        item["rate_currency"] = fmt_money(
            item_price[0].price_list_rate if item_price else 0.0,
            currency=global_defaults.get("default_currency"),
        )
        item["rate"] = item_price[0].price_list_rate if item_price else 0.0
    return items

@frappe.whitelist()
def prepare_quotation_totals(**kwargs):
    try:
        data = kwargs
        # Fetch customer name using the logged-in user session
        data['party_name'] = frappe.db.get_value("Customer", {"custom_user": frappe.session.user}, ["name"])

        # Ensure customer is fetched successfully
        if not data['party_name']:
            frappe.throw(_("Customer not found for the current user session."))

        ess_settings = get_ess_settings()
        data['valid_till'] = today()  # Use today's date if not provided
        
        # Use valid_till from data, not undefined variable
        for item in data.get("items", []):
            item["valid_till"] = data['valid_till']
            item["warehouse"] = ess_settings.get("default_warehouse")
        
        global_defaults = get_global_defaults()
        data['default_currency'] = global_defaults.get("default_currency", "INR")
        
        # frappe.throw(str(data))  # Fallback to INR if not set
        
        # Use data['default_currency'] instead of undefined variable default_currency
        sales_order_doc = frappe.get_doc(dict(
            doctype="Quotation", 
            company=global_defaults.get("default_company"),
            currency=data['default_currency'],  # Explicitly set the default currency
        ))
        # Update the sales order document with the provided data
        sales_order_doc.update(data)
        
        # Check if exchange rate is required
        if not sales_order_doc.currency:
            frappe.throw(_("Currency is missing for the quotation."))
        
        # Set missing values and calculate taxes and totals
        sales_order_doc.run_method("set_missing_values")
        sales_order_doc.run_method("calculate_taxes_and_totals")
        
        # Serialize the document and return relevant fields
        sales_order_doc_json = json.loads(sales_order_doc.as_json())
        order_data = prepare_json_data(
            ["taxes_and_charges", "total_taxes_and_charges", "net_total", "discount_amount", "grand_total"],
            sales_order_doc_json,
        )
        
        gen_response(200, "Quotation details fetched successfully", sales_order_doc_json)
    
    except Exception as e:
        return exception_handel(e)



def get_order_details_with_currency(sales_order_doc, currency):
    order_response_dict = {}
    for response_fields in [
        "total_taxes_and_charges",
        "net_total",
        "discount_amount",
        "grand_total",
    ]:
        order_response_dict[response_fields] = fmt_money(
            sales_order_doc.get(response_fields),
            currency=currency,
        )
    return order_response_dict

@frappe.whitelist(allow_guest=True)
def create_quotation(**kwargs):
    try:
        data = kwargs
        sales_order_doc = frappe.get_doc(
                dict(doctype="mobile App Enquire")
            )
            # delivery_date = data.get("valid_till")
            # for item in data.get("items"):
            #     item["delivery_date"] = delivery_date
            #     item["warehouse"] = default_warehouse
        sales_order_doc.update(data)
        sales_order_doc.insert()
        # Respond with success message
        return gen_response(200, _("Quotation created/updated successfully."), sales_order_doc.name)

    except frappe.PermissionError:
        return gen_response(500, _("Not permitted to create/update quotation."))
    except Exception as e:
        return exception_handel(e)


def _create_update_quotation(data, quotation_doc, default_warehouse):
    valid_till = data.get("valid_till")
    for item in data.get("items"):
        item["valid_till"] = valid_till
        item["warehouse"] = default_warehouse
    quotation_doc.update(data)
    quotation_doc.run_method("set_missing_values")
    quotation_doc.run_method("calculate_taxes_and_totals")
    quotation_doc.save()


@frappe.whitelist()
def get_item_group_list(filters=None):
    try:
        if not filters:
            filters = []
        filters.append(["Item Group", "show_in_mobile", "=", 1])
        item_group_list = frappe.get_list(
            "Item Group", fields=["name"], filters=filters
        )
        gen_response(200, "Item group list get successfully", item_group_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for item")
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_lead_list():
    try:
        lead_list = frappe.get_all("Lead", fields=["name"])
        gen_response(200, "Lead list get successfully", lead_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for lead")
    except Exception as e:
        return exception_handel(e)


# @frappe.whitelist()
# def download_quotation_pdf(id):
#     try:
#         quotation_doc = frappe.get_doc("Quotation", id)
#         default_print_format = (
#             frappe.db.get_value(
#                 "Property Setter",
#                 dict(property="default_print_format", doc_type=quotation_doc.doctype),
#                 "value",
#             )
#             or "Standard"
#         )
#         download_pdf(
#             quotation_doc.doctype,
#             quotation_doc.name,
#             default_print_format,
#             quotation_doc,
#         )
#     except Exception as e:
#         return exception_handler(e)