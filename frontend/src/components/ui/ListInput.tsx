import { useEffect, useState } from "react";
import { commaList } from "../../utils/format";

interface Props {
  label: string;
  value: string[];
  onChange: (items: string[]) => void;
  required?: boolean;
  placeholder?: string;
}

/** Keep unfinished separators while typing; send normalized values to the API model. */
export function ListInput({
  label,
  value,
  onChange,
  required,
  placeholder,
}: Props) {
  const [text, setText] = useState(value.join(", "));
  const signature = JSON.stringify(value);
  useEffect(() => {
    setText((current) =>
      JSON.stringify(commaList(current)) === signature
        ? current
        : (JSON.parse(signature) as string[]).join(", "),
    );
  }, [signature]);
  return (
    <label>
      <span>{label}</span>
      <input
        required={required}
        value={text}
        placeholder={placeholder}
        onChange={(event) => {
          setText(event.target.value);
          onChange(commaList(event.target.value));
        }}
      />
    </label>
  );
}
