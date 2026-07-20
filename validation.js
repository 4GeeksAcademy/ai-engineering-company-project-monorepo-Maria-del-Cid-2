document.addEventListener("DOMContentLoaded", () => {
	const menuButton = document.querySelector("[data-menu-button]");
	const mobileMenu = document.querySelector("[data-mobile-menu]");
	const form = document.querySelector("#nexova-form");
	const successCard = document.querySelector("#form-success-card");
	const countryInput = document.querySelector("#country");
	const cityInput = document.querySelector("#city");
	const locationStatus = document.querySelector("#location-status");
	const countryOptions = document.querySelector("#country-options");
	const cityOptions = document.querySelector("#city-options");
	const serviceCheckboxes = document.querySelectorAll("[data-service-checkbox]");
	const servicesFieldset = document.querySelector("#services-fieldset");
	const servicesError = document.querySelector("#services-error");
	const privacyConsent = document.querySelector("#privacy-consent");
	const privacyConsentWrapper = document.querySelector("#privacy-consent-wrapper");
	const locationCatalog = window.NEXOVA_LOCATION_CATALOG || { countries: [], citiesByCountry: {} };
	let citiesByCountry = locationCatalog.citiesByCountry || {};
	const formFields = form ? Array.from(form.querySelectorAll("input[list], input[type='text'], input[type='tel'], input[type='email']")) : [];

	if (!menuButton || !mobileMenu) {
		return;
	}

	const closeMenu = () => {
		mobileMenu.classList.add("hidden");
		menuButton.setAttribute("aria-expanded", "false");
		menuButton.setAttribute("aria-label", "Abrir menú principal");
	};

	const toggleMenu = () => {
		const isOpen = menuButton.getAttribute("aria-expanded") === "true";
		mobileMenu.classList.toggle("hidden", isOpen);
		menuButton.setAttribute("aria-expanded", String(!isOpen));
		menuButton.setAttribute("aria-label", isOpen ? "Abrir menú principal" : "Cerrar menú principal");
	};

	menuButton.addEventListener("click", toggleMenu);
	mobileMenu.querySelectorAll("a").forEach((link) => {
		link.addEventListener("click", closeMenu);
	});

	if (countryInput && cityInput && cityOptions && countryOptions) {
		const setLocationStatus = (message) => {
			if (locationStatus) {
				locationStatus.textContent = message;
			}
		};

		const normalizeCountryName = (value) => value.trim().toLowerCase();

		const populateCountryOptions = () => {
			countryOptions.innerHTML = "";

			locationCatalog.countries.forEach((countryName) => {
				const option = document.createElement("option");
				option.value = countryName;
				countryOptions.appendChild(option);
			});

			countryInput.disabled = locationCatalog.countries.length === 0;
			cityInput.disabled = true;

			if (locationCatalog.countries.length === 0) {
				setLocationStatus("No se pudo cargar el catálogo local de países y ciudades.");
				return;
			}

			setLocationStatus("Países cargados. Empieza a escribir para ver sugerencias.");
		};

		const syncCities = () => {
			const selectedCountry = countryInput.value.trim();
			const matchedCountry = Object.keys(citiesByCountry).find(
				(countryName) => normalizeCountryName(countryName) === normalizeCountryName(selectedCountry)
			);
			const cities = matchedCountry ? citiesByCountry[matchedCountry] : [];

			cityOptions.innerHTML = "";
			cityInput.value = "";
			cityInput.disabled = cities.length === 0;

			if (cities.length === 0) {
				setLocationStatus(selectedCountry ? "No hay ciudades cargadas para ese país. Selecciona un país válido de la lista." : "Selecciona un país para habilitar la ciudad.");
				return;
			}

			cities.forEach((city) => {
				const option = document.createElement("option");
				option.value = city;
				cityOptions.appendChild(option);
			});

			setLocationStatus(`Se han cargado ${cities.length} ciudades para ${matchedCountry}.`);
		};

		populateCountryOptions();
		countryInput.addEventListener("input", syncCities);
		countryInput.addEventListener("change", syncCities);
	}

	const showFieldError = (field, message) => {
		const errorTargetId = field.dataset.errorTarget;
		const errorNode = errorTargetId ? document.getElementById(errorTargetId) : null;

		field.setAttribute("aria-invalid", "true");
		field.classList.remove("border-brand-lightgray", "focus:border-brand-orange", "focus:ring-brand-orange/15");
		field.classList.add("border-red-600", "focus:border-red-600", "focus:ring-red-100");

		if (errorNode) {
			errorNode.classList.remove("hidden");
			errorNode.classList.add("flex");
			const errorText = errorNode.querySelector("span");
			if (errorText) {
				errorText.textContent = message;
			}
		}
	};

	const clearFieldError = (field) => {
		const errorTargetId = field.dataset.errorTarget;
		const errorNode = errorTargetId ? document.getElementById(errorTargetId) : null;

		field.setAttribute("aria-invalid", "false");
		field.classList.remove("border-red-600", "focus:border-red-600", "focus:ring-red-100");
		field.classList.add("border-brand-lightgray", "focus:border-brand-orange", "focus:ring-brand-orange/15");

		if (errorNode) {
			errorNode.classList.add("hidden");
			errorNode.classList.remove("flex");
		}
	};

	const showServicesError = (message) => {
		if (servicesFieldset) {
			servicesFieldset.classList.remove("border-brand-lightgray");
			servicesFieldset.classList.add("border-red-600", "ring-2", "ring-red-100");
		}

		serviceCheckboxes.forEach((checkbox) => {
			checkbox.setAttribute("aria-invalid", "true");
		});

		if (servicesError) {
			servicesError.classList.remove("hidden");
			servicesError.classList.add("flex");
			const errorText = servicesError.querySelector("span");
			if (errorText) {
				errorText.textContent = message;
			}
		}
	};

	const clearServicesError = () => {
		if (servicesFieldset) {
			servicesFieldset.classList.remove("border-red-600", "ring-2", "ring-red-100");
			servicesFieldset.classList.add("border-brand-lightgray");
		}

		serviceCheckboxes.forEach((checkbox) => {
			checkbox.setAttribute("aria-invalid", "false");
		});

		if (servicesError) {
			servicesError.classList.add("hidden");
			servicesError.classList.remove("flex");
		}
	};

	const showPrivacyError = (message) => {
		if (privacyConsentWrapper) {
			privacyConsentWrapper.classList.remove("border-brand-lightgray");
			privacyConsentWrapper.classList.add("border-red-600", "ring-2", "ring-red-100");
		}

		if (privacyConsent) {
			showFieldError(privacyConsent, message);
		}
	};

	const clearPrivacyError = () => {
		if (privacyConsentWrapper) {
			privacyConsentWrapper.classList.remove("border-red-600", "ring-2", "ring-red-100");
			privacyConsentWrapper.classList.add("border-brand-lightgray");
		}

		if (privacyConsent) {
			clearFieldError(privacyConsent);
		}
	};

	const validateTextField = (field) => {
		const value = field.value.trim();

		if (!value) {
			showFieldError(field, "Este campo es obligatorio.");
			return false;
		}

		if (field.name === "contactEmail" && !field.checkValidity()) {
			showFieldError(field, "Introduce un email profesional válido.");
			return false;
		}

		if (field.name === "contactPhone" && value.replace(/\D/g, "").length < 7) {
			showFieldError(field, "Introduce un teléfono de contacto válido.");
			return false;
		}

		if (field.name === "companyCif" && !/^[A-Za-z]\d{7}[A-Za-z0-9]$|^[A-Za-z0-9]\d{7}[A-Za-z0-9]$/.test(value)) {
			showFieldError(field, "Introduce un CIF con un formato similar a B12345678.");
			return false;
		}

		if (field.name === "country" && !Object.keys(citiesByCountry).some((countryName) => countryName.toLowerCase() === value.toLowerCase())) {
			showFieldError(field, "Selecciona un país válido de la lista disponible.");
			return false;
		}

		if (field.name === "city") {
			const selectedCountry = countryInput ? countryInput.value.trim() : "";
			const matchedCountry = Object.keys(citiesByCountry).find((countryName) => countryName.toLowerCase() === selectedCountry.toLowerCase());
			const availableCities = matchedCountry ? citiesByCountry[matchedCountry] : [];

			if (!availableCities.some((cityName) => cityName.toLowerCase() === value.toLowerCase())) {
				showFieldError(field, "Selecciona una ciudad válida del país elegido.");
				return false;
			}
		}

		clearFieldError(field);
		return true;
	};

	const validateServices = () => {
		const hasCheckedService = Array.from(serviceCheckboxes).some((checkbox) => checkbox.checked);

		if (!hasCheckedService) {
			showServicesError("Selecciona al menos un servicio de interés.");
			return false;
		}

		clearServicesError();
		return true;
	};

	const validatePrivacyConsent = () => {
		if (!privacyConsent || privacyConsent.checked) {
			clearPrivacyError();
			return true;
		}

		showPrivacyError("Debes aceptar el tratamiento de datos personales para continuar.");
		return false;
	};

	const resetValidationState = () => {
		formFields.forEach((field) => {
			clearFieldError(field);
		});

		clearServicesError();
		clearPrivacyError();
	};

	if (serviceCheckboxes.length > 0) {
		const syncServiceValidation = () => {
			const hasCheckedService = Array.from(serviceCheckboxes).some((checkbox) => checkbox.checked);

			serviceCheckboxes.forEach((checkbox, index) => {
				checkbox.required = !hasCheckedService && index === 0;
				checkbox.setCustomValidity(hasCheckedService ? "" : "Selecciona al menos un servicio.");
			});
		};

		syncServiceValidation();
		serviceCheckboxes.forEach((checkbox) => {
			checkbox.addEventListener("change", syncServiceValidation);
		});
	}

	formFields.forEach((field) => {
		field.addEventListener("input", () => {
			if (field.getAttribute("aria-invalid") === "true") {
				validateTextField(field);
			}
		});

		field.addEventListener("blur", () => {
			if (field.value.trim()) {
				validateTextField(field);
			}
		});
	});

	if (privacyConsent) {
		privacyConsent.addEventListener("change", validatePrivacyConsent);
	}

	if (form) {
		form.addEventListener("submit", (event) => {
			event.preventDefault();

			resetValidationState();

			const areFieldsValid = formFields.every((field) => validateTextField(field));
			const areServicesValid = validateServices();
			const isPrivacyConsentValid = validatePrivacyConsent();

			if (!areFieldsValid || !areServicesValid || !isPrivacyConsentValid) {
				const firstInvalidField = form.querySelector("[aria-invalid='true']");
				if (firstInvalidField) {
					firstInvalidField.focus();
				}
				return;
			}

			form.classList.add("hidden");
			if (successCard) {
				successCard.classList.remove("hidden");
			}
		});

		form.addEventListener("reset", () => {
			requestAnimationFrame(() => {
				resetValidationState();
				if (countryInput) {
					countryInput.value = "";
				}
				if (cityInput) {
					cityInput.value = "";
					cityInput.disabled = true;
				}
				if (cityOptions) {
					cityOptions.innerHTML = "";
				}
				if (successCard) {
					successCard.classList.add("hidden");
				}
				form.classList.remove("hidden");
				if (locationCatalog.countries.length > 0 && locationStatus) {
					locationStatus.textContent = "Países cargados. Empieza a escribir para ver sugerencias.";
				}
			});
		});
	}
});
