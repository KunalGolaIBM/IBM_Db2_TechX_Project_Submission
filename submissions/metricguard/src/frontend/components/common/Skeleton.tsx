import clsx from "clsx";
export const Skeleton = ({ className }: { className?: string }) => <div aria-hidden className={clsx("skeleton", className)} />;
