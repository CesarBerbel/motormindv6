import api from "../api/client";
import { onlyDigits, maskCep } from "../workshopOptions";

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
  if (data?.cep) return Array.isArray(data.cep) ? data.cep.join(" ") : data.cep;
  if (data?.detail) return data.detail;
  if (error?.message) return error.message;
  return "Não foi possível buscar o CEP.";
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
    // Fallback mantém a busca funcionando em desenvolvimento quando o backend estiver antigo,
    // mas em produção o caminho preferencial é o proxy autenticado /api/workshop/cep/.
    try {
      const response = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
      if (!response.ok) throw new Error("Não foi possível consultar o CEP. Tente novamente.");
      const data = await response.json();
      if (data.erro) throw new Error("CEP não encontrado na base pública ViaCEP.");
      return normalizeCepPayload(data, digits);
    } catch {
      throw new Error(friendlyCepError(backendError));
    }
  }
}
