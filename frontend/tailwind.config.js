/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      boxShadow: {
        soft: "0 12px 28px rgba(15, 23, 42, 0.08)",
      },
    },
  },
  safelist: [
    "w-1/12", "w-2/12", "w-3/12", "w-4/12", "w-5/12", "w-6/12", "w-7/12", "w-8/12", "w-9/12", "w-10/12", "w-11/12", "w-full",
    "md:w-1/12", "md:w-2/12", "md:w-3/12", "md:w-4/12", "md:w-5/12", "md:w-6/12", "md:w-7/12", "md:w-8/12", "md:w-9/12", "md:w-10/12", "md:w-11/12", "md:w-full",
    "lg:w-1/12", "lg:w-2/12", "lg:w-3/12", "lg:w-4/12", "lg:w-5/12", "lg:w-6/12", "lg:w-7/12", "lg:w-8/12", "lg:w-9/12", "lg:w-10/12", "lg:w-11/12", "lg:w-full",
    "xl:w-1/12", "xl:w-2/12", "xl:w-3/12", "xl:w-4/12", "xl:w-5/12", "xl:w-6/12", "xl:w-7/12", "xl:w-8/12", "xl:w-9/12", "xl:w-10/12", "xl:w-11/12", "xl:w-full"
  ]
};
