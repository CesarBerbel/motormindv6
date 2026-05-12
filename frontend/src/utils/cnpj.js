import api from "../api/client";
import { maskCep, maskCpfCnpj, onlyDigits } from "../workshopOptions";
import { maskBrazilPhone } from "./phone";

function friendlyCnpjError(error) {
  const data = error?.response?.data;
  if (data?.cnpj) return Array.isArray(data.cnpj) ? data.cnpj.join(" ") : data.cnpj;
  if (data?.detail) return data.detail;
  if (error?.message && !String(error.message).includes("Request failed")) return error.message;
  return "Não foi possível buscar o CNPJ agora. Preencha os dados manualmente ou tente novamente em instantes.";
}

export async function lookupCnpj(cnpj) {
  const digits = onlyDigits(cnpj);
  if (digits.length !== 14) {
    throw new Error("Informe um CNPJ com 14 dígitos antes de buscar.");
  }

  try {
    const { data } = await api.get("/workshop/cnpj/", { params: { cnpj: digits } });
    return {
      ...data,
      document: maskCpfCnpj(data?.document || digits),
      zip_code: maskCep(data?.zip_code || ""),
      phone: data?.phone ? maskBrazilPhone(data.phone) : "",
    };
  } catch (error) {
    throw new Error(friendlyCnpjError(error));
  }
}
