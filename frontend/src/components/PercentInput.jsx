import React from "react";
import { InputGroup } from "../ui/TailwindPrimitives.jsx";
import IntegerInput from "./IntegerInput";

export default function PercentInput({ value, onChange, min = "0", max = "100", step = "0.01", placeholder = "0,00", ...props }) {
  return (
    <InputGroup {...props}>
      <IntegerInput
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        aria-label="Percentual de desconto"
      />
      <InputGroup.Text>%</InputGroup.Text>
    </InputGroup>
  );
}
