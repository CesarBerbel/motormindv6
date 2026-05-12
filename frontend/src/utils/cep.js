import api from "../api/client";
import { onlyDigits, maskCep } from "../workshopOptions";

const CEP_NOT_FOUND_MESSAGE = "Não encontrei esse CEP. Confira os 8 dígitos ou preencha o endereço manualmente.";

function normalizeCepPayload(data, digits) {
  return {
    zip_code: maskCep(data?.zip_code || data?.cep || digits),
    address_line: data?.address_line || data?.logradouro || "",
    district: data?.district || data?.bairro || "",
    city: data?.city || data?.localidade || "",
    state: data?.state || data?.uf || "",
    country: data?.country || "Brasil",
  };
}

function friendlyCepError(error) {
  const data = error?.response?.data;
  if (error?.message === "CEP_NOT_FOUND") return CEP_NOT_FOUND_MESSAGE;
  if (error?.response?.status === 404) return data?.detail || CEP_NOT_FOUND_MESSAGE;
  if (data?.cep) return Array.isArray(data.cep) ? data.cep.join(" ") : data.cep;
  if (data?.detail) return data.detail;
  if (error?.message && !String(error.message).includes("Request failed")) return error.message;
  return "Não foi possível buscar o CEP agora. Preencha o endereço manualmente ou tente novamente em instantes.";
}

export async function lookupCep(cep) {
  const digits = onlyDigits(cep);
  if (digits.length !== 8) {
    throw new Error("Informe um CEP com 8 dígitos antes de buscar.");
  }

  try {
    const { data } = await api.get("/workshop/cep/", { params: { cep: digits } });
    return normalizeCepPayload(data, digits);
  } catch (backendError) {
    try {
      const response = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
      if (!response.ok) throw backendError;
      const data = await response.json();
      if (data.erro) throw new Error("CEP_NOT_FOUND");
      return normalizeCepPayload(data, digits);
    } catch (fallbackError) {
      if (fallbackError?.message === "CEP_NOT_FOUND") throw new Error(CEP_NOT_FOUND_MESSAGE);
      throw new Error(friendlyCepError(backendError));
    }
  }
}
