/** A translation of a Hungarian source dictionary: exactly the same keys, any string values. */
export type Messages<T> = { readonly [K in keyof T]: string };

/** Placeholder names in a message literal: "{date} és {n}" -> "date" | "n". */
export type ParamNames<S extends string> = S extends `${string}{${infer Name}}${infer Rest}`
	? Name | ParamNames<Rest>
	: never;

export type ParamValue = string | number;
