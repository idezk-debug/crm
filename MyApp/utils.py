import phonenumbers

MIN_PASSWORD_LENGTH = 8


def validate_password(password):
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return True, ""


def validate_phone_number(country_code, phone_number):
    phone_number = (phone_number or "").strip()
    country_code = (country_code or "").strip()

    if not phone_number:
        return False, "Phone number is required."

    if not country_code or not country_code.startswith("+"):
        return False, "Please select a valid country code."

    try:
        parsed = phonenumbers.parse(f"{country_code}{phone_number}", None)
    except phonenumbers.NumberParseException:
        return False, "Invalid phone number format."

    if not phonenumbers.is_valid_number(parsed):
        return False, "This phone number is not valid for the selected country."

    return True, ""
